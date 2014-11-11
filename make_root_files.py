#!/usr/bin/env python

import math
import optparse
import os
import ROOT as r

from cfg import masses_spin0 as masses


def inputFile():
    parser = optparse.OptionParser("usage: %prog xyz.root")
    options, args = parser.parse_args()
    if len(args) != 1 or not args[0].endswith(".root"):
        parser.print_help()
        exit()
    return args[0]


def mkdir(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != 17:
            raise e


def combineBinContentAndError(h, binToContainCombo, binToBeKilled):
    c = h.GetBinContent(binToContainCombo) + h.GetBinContent(binToBeKilled)
    e = h.GetBinError(binToContainCombo)**2 + h.GetBinError(binToBeKilled)**2
    e = e**0.5

    h.SetBinContent(binToBeKilled, 0.0)
    h.SetBinContent(binToContainCombo, c)

    h.SetBinError(binToBeKilled, 0.0)
    h.SetBinError(binToContainCombo, e)


def shift(h):
    n = h.GetNbinsX()
    combineBinContentAndError(h, n, n+1)  # overflows
    combineBinContentAndError(h, 1, 0)  # underflows


def isData(proc):
    return proc.startswith("data")


def isSignal(proc):
    for prefix in ["H2hh", "ggA", "bbH"]:
        if proc.startswith(prefix):
            return True
    return False


def isAntiIsoData(proc):
    return proc == "dataOSRelax"


def histos(fileName="", bins=None, procs=[], var="", rescaleX=False, cuts={}, category=""):
    assert fileName
    assert bins

    # rescale so that bin width is 1.0
    if rescaleX:
        assert bins[0]
        binWidth = (bins[2] - bins[1]) / bins[0]
        assert binWidth
        factor = 1.0 / binWidth
        bins = (bins[0], bins[1] * factor, bins[2] * factor)
        var = "(%g*%s)" % (factor, var)

    f = r.TFile(fileName)
    tree = f.Get("eventTree")
    out = {}

    for proc in procs:
        h = r.TH1D(proc, proc+";%s;events / bin" % var, *bins)
        h.Sumw2()
        w = "1.0" if isData(proc) else "triggerEff"
        cutString = '(sampleName=="%s")' % proc
        if category:
            cutString += ' && (Category=="%s")' % category

        for cutVar, (cutMin, cutMax) in sorted(cuts.iteritems()):
            if cutMin is not None:
                cutString += " && (%g < %s)" % (cutMin, cutVar)
            if cutMax is not None:
                cutString += " && (%s < %g)" % (cutVar, cutMax)

        tree.Draw("%s>>%s" % (var, proc), '(%s)*(%s)' % (w, cutString))
        h.SetDirectory(0)
        shift(h)
        out[proc] = h
        if isAntiIsoData(proc):
            applyLooseToTight(h, f, category)

    applySampleWeights(out, f)
    f.Close()
    return out


def applySampleWeights(hs={}, tfile=None):
    numer = tfile.Get("xs")
    denom = tfile.Get("initEvents")
    xNumer = numer.GetXaxis()
    xDenom = denom.GetXaxis()

    for proc, h in hs.iteritems():
        if isData(proc):
            continue

        for iBin in range(1, 1 + numer.GetNbinsX()):
            if xNumer.GetBinLabel(iBin) == proc:
                xs = numer.GetBinContent(iBin)
                if proc.startswith("H2hh"):
                    xs = 1.0e3 # 1 pb
                h.Scale(xs)
                h.GetZaxis().SetTitle("@ %g fb" % xs)
                #print proc, xs

        for iBin in range(1, 1 + denom.GetNbinsX()):
            if xDenom.GetBinLabel(iBin) == proc:
                content = denom.GetBinContent(iBin)
                assert content, "%s_%d" % (proc, iBin)
                h.Scale(1.0 / content)


def applyLooseToTight(h=None, tfile=None, category=""):
    hFactor = tfile.Get("L_to_T_%s" % category)
    factor = hFactor.GetBinContent(1)
    factor *= 0.9
    print "FIXME: get EWK contamination from file (currently hard-coded)"
    h.Scale(factor)


def describe(h, prefix):
    print "%s: %s" % (prefix, h.GetXaxis().GetTitle())
    headers = "bin       x         cont  +-   err    (   rel)"
    print headers
    print "-" * len(headers)
    for iBinX in range(1, 1 + h.GetNbinsX()):
        x = h.GetBinCenter(iBinX)
        c = h.GetBinContent(iBinX)
        e = h.GetBinError(iBinX)
        s = " %2d   %9.2e   %7.1e +- %7.1e" % (iBinX, x, c, e)
        if c:
            s += "  (%5.1f%s)" % (100.*e/c, "%")
        print s
    print


def cutDesc(cuts):
    descs = []
    for cutVar, (cutMin, cutMax) in sorted(cuts.iteritems()):
        cutDesc = cutVar
        if cutMin is not None:
            cutDesc = "%.1f.%s" % (cutMin, cutDesc)
        if cutMax is not None:
            cutDesc = "%s.%.1f" % (cutDesc, cutMax)
        descs.append(cutDesc)
    return "_".join(descs)


def outFileName(sFactor, sKey, var, cuts):
    stem = "root/"
    mkdir(stem)

    if sFactor:
        stem += "%dx%s" % (sFactor, sKey.replace("H2hh", ""))
    stem += var
    if cutDesc(cuts):
        stem += "_%s" % cutDesc(cuts)
    return "%s.root" % stem


def go(inFile="", sFactor=None, sKey="", bins=None, var="", rescaleX=True,
       cuts=None, lumi=19.7):

    assert type(sFactor) is int, type(sFactor)
    assert bins
    assert var

    procs = {"tt_full": "TT",
             "tt_semi": "tt_semi",
             "ZZ": "VV",
             "W1JetsToLNu": "W",
             "W2JetsToLNu": "W2",
             "W3JetsToLNu": "W3",
             "DY1JetsToLL": "ZTT",
             "DY2JetsToLL": "DY2",
             "DY3JetsToLL": "DY3",
             "dataOSRelax": "QCD",
             }

    fakeSigs = ["ggAToZhToLLTauTau", "ggAToZhToLLBB", "bbH"]
    print "FIXME: include", fakeSigs
    for m in masses:
        procs["H2hh%3d" % m] = "ggHTohhTo2Tau2B%3d" % m
        for stem in fakeSigs:
            sig = "%s%3d" % (stem, m)
            procs[sig] = sig

    kargs = {"procs": procs.keys(),
             "bins": bins,
             "var": var,
             "cuts": cuts,
             "rescaleX": rescaleX,
             "fileName": inFile,
             }

    print "FIXME: include variations"
    f = r.TFile(outFileName(sFactor, sKey, var, cuts), "RECREATE")
    for category, tag in {"2M": "tauTau_2jet2tag",
                          "1M": "tauTau_2jet1tag",
                          }.iteritems():
        hs = histos(category=category, **kargs)
        print
        print "cuts:", cuts
        for target, sources in {"tt_full": ["tt_semi"],
                                "DY1JetsToLL": ["DY2JetsToLL", "DY3JetsToLL"],
                                "W1JetsToLNu": ["W2JetsToLNu", "W3JetsToLNu"],
                                }.iteritems():
            for source in sources:
                hs[target].Add(hs[source])
                del hs[source]
        f.mkdir(tag).cd()
        oneTag(tag, hs, procs, lumi, sKey, sFactor)
    f.Close()


def printIntegrals(lst=[], lumi=None):
    hyphens = "-"*71
    print hyphens
    for tag, proc, integral in sorted(lst):
        print tag, proc.ljust(30), "%9.3f" % integral, " (for %4.1f/fb)" % lumi
    print hyphens
    print


def oneTag(tag, hs, procs, lumi, sKey, sFactor):
    integrals = []
    # scale and write
    for (proc, h) in hs.iteritems():
        if not isData(proc):
            h.Scale(lumi)
        #h.Print("all")
        if isSignal(proc) and "350" not in proc:
            pass
        else:
            integrals.append((tag, proc, h.Integral(0, 2 + h.GetNbinsX())))

        nom = procs[proc]
        h.Write(nom)
        # fake
        for var in ["Up", "Down"]:
            h.Write("%s_CMS_scale_t_tautau_8TeV%s" % (nom, var))

    printIntegrals(integrals, lumi)

    # make a fake dataset
    d = hs["tt_full"].Clone("data_obs")
    d.Add(hs["ZZ"])
    d.Add(hs["dataOSRelax"])

    describe(d, tag)
    zTitle = "Observed = floor(sum(bkg))"
    if sFactor:
        d.Add(hs[sKey], sFactor)
        if sFactor != 1:
            zTitle += " + %d#times" % sFactor
        else:
            zTitle += " + "
        zTitle += "%s %s)" % (sKey.replace("2hh", ""), hs[sKey].GetZaxis().GetTitle())
    else:
        zTitle += ")"

    d.GetZaxis().SetTitle(zTitle)


    # integerize
    for iBin in range(1, 1 + d.GetNbinsX()):
        c = math.floor(d.GetBinContent(iBin))
        d.SetBinContent(iBin, c)
        d.SetBinError(iBin, math.sqrt(max(0.0, c)))

    d.Write()


def loop(inFile="", specs={}):
    for spec in specs:
        for mInj in masses[:1]:
            for sFactor in [0, 1, 2, 4][:1]:
                go(inFile=inFile,
                   sFactor=sFactor,
                   sKey="H2hh%3d" % mInj,
                   rescaleX=True,
                   **spec)


def specs1():
    return [#{"var": "BDT_260", "bins": ( 4, -0.55, 0.25), "cuts": {}},
            #{"var": "BDT_300", "bins": ( 4, -0.50, 0.30), "cuts": {}},
            #{"var": "BDT_350", "bins": ( 4, -0.45, 0.35), "cuts": {}},
            #{"var": "mJJReg",  "bins": (15, 50.0, 200.0), "cuts": {}},
            {"var": "mJJ",     "bins": (15, 50.0, 200.0), "cuts": {}},
            
            {"var": "svMass",  "bins": (15, 50.0, 200.0), "cuts": {}},
            {"var": "svMass",  "bins": (10, 50.0, 250.0), "cuts": {"mJJ": (90.0, 140.0)}},
            
            {"var": "fMass",   "bins": (7, 200.0, 480.0), "cuts": {}},
            {"var": "fMassKinFit", "bins": (7, 200.0, 480.0), "cuts": {}},
            
            {"var": "fMass",   "bins": (7, 200.0, 480.0), "cuts": {"mJJ": (90.0, 140.0)}},  # , "svMass": (95.0, 155.0)}},
            {"var": "fMassKinFit", "bins": (7, 200.0, 480.0), "cuts": {"mJJ": (90.0, 140.0)}},  # , "svMass": (95.0, 155.0)}},
            
            {"var": "chi2KinFit", "bins": (10, 0.0, 100.0), "cuts": {}},
            {"var": "chi2KinFit", "bins": (10, 0.0, 100.0), "cuts": {}},
            
            #{"var": "fMass",   "bins": (5, 200.0, 400.0), "cuts": {"mJJ": (90.0, 140.0), "svMass": (95.0, 155.0)}},
            #{"var": "fMassKinFit", "bins": (5, 200.0, 400.0), "cuts": {"mJJ": (90.0, 140.0), "svMass": (95.0, 155.0)}},
            ]


def specs2():
    out = []
    for var, bins in [("svMass",      (15,  50.0, 200.0)),
                      ("fMass",       ( 7, 200.0, 480.0)),
                     #("fMassKinFit", ( 7, 200.0, 480.0)),
                     #("fMassKinFit", ( 6, 250.0, 490.0)),
                      ("fMassKinFit", (12, 250.0, 490.0)),
                     #("fMassKinFit", (24, 250.0, 490.0)),
                      ("chi2KinFit",  (11, -10.0, 100.0)),
                      ]:
        for cut in [{},
                    {"mJJ": (90.0, 140.0)},
                    #{"chi2KinFit": (0.0, 40.0)},
                    {"chi2KinFit": (0.0, 10.0)},
                    ]:
            out.append({"var": var, "bins": bins, "cuts": cut})
    return out


def specs3():
    out = []
    for var, bins in [("BDT_260", (8, -0.6, 0.2)),
                      ("BDT_270", (8, -0.6, 0.2)),
                      ("BDT_280", (8, -0.6, 0.2)),
                      ("BDT_290", (8, -0.6, 0.2)),
                      ("BDT_300", (8, -0.6, 0.2)),
                      ("BDT_310", (8, -0.6, 0.2)),
                      ("BDT_320", (8, -0.6, 0.2)),
                      ("BDT_330", (8, -0.6, 0.2)),
                      ("BDT_340", (8, -0.6, 0.2)),
                      ("BDT_350", (8, -0.6, 0.2)),
                      ]:
        out.append({"var": var, "bins": bins, "cuts": {}})
    return out


def specs4():
    cuts = {#"mJJ": (90.0, 140.0),
            #"svMass": (90.0, 140.0),
            #"CSVJ2":  (0.679, None),
            #"CSVJ2":  (0.244, 0.679),
            #"chi2KinFit2": (0.0, 10.0),
            }

    return [#{"var": "fMass",       "bins": ( 5, 250.0, 450.0), "cuts": {"BDT_300_3": (0.0, None)}, },
            #{"var": "fMassKinFit", "bins": ( 5, 250.0, 450.0), "cuts": {"BDT_300_3": (0.0, None)}, },
            #{"var": "fMass",       "bins": ( 4, 250.0, 410.0), "cuts": {"BDT_300_3": (0.2, None)}, },
            #{"var": "fMassKinFit", "bins": ( 4, 250.0, 410.0), "cuts": {"BDT_300_3": (0.2, None)}, },
            #{"var": "fMass",       "bins": ( 4, 250.0, 410.0), "cuts": cuts},
            {"var": "fMassKinFit", "bins": ( 4, 250.0, 410.0), "cuts": cuts},
            #{"var": "chi2KinFit", "bins":  (4, -20.0, 60.0), "cuts": cuts},
            ]


def specs5():
    out = []
    for xMin in [80, 85, 90, 95, 100, 105, 110, 115, 120]:
        for xMax in [130, 135, 140, 145, 150]:
            twoCuts = {"mJJ": (xMin, xMax), "svMass": (xMin, xMax)}
            out.append({"var": "fMassKinFit",
                        "bins": ( 4, 250.0, 410.0),
                        "cuts": twoCuts})
    return out


if __name__ == "__main__":
    r.gROOT.SetBatch(True)
    r.gErrorIgnoreLevel = 2000

    loop(inFile=inputFile(), specs=specs4())

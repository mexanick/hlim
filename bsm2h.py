#!/usr/bin/env python

import os
import sys
import ROOT as r
from h2bsm import xs_fb


def merge(stems=None, inDir=None, outDir=None, hName=None, suffix=None, tag="", dest="BSM3G", scale_signal_to_pb=False):
    outFile = r.TFile("%s/src/auxiliaries/shapes/%s/htt_%s.inputs-Zp-13TeV.root" % (os.environ["CMSSW_BASE"], dest, tag), "RECREATE")
    outFile.mkdir(outDir)

    name_map = [("QCD_all", "QCD"),
                ("ZPrime_", "ggH"),
                ("ZprimeToTauTau_M_", "ggH"),
                ("Data", "data_obs"),
                ("Diboson", "VV"),
                ("TTBar", "TT"),
                ("WJets", "W"),
                ("ZJets", "ZTT"),

                ("eleTau_Z", "eleTau_ZTT"),
                ("emu_Z", "emu_ZTT"),
                ("eleTau_", ""),
                ("emu_", ""),
                ]

    for stem in stems:
        inFileName = inDir + stem + suffix
        inFile = r.TFile(inFileName)
        h1 = inFile.Get(hName)
        if not h1:
            sys.exit("%s:%s not found" % (inFileName, hName))

        proc = stem
        for old, new in name_map:
            proc = proc.replace(old, new)

        h = h1.Clone(proc)
        h.SetDirectory(0)
        inFile.Close()

        if scale_signal_to_pb and proc.startswith("ggH"):
            mass = int(proc.replace("ggH", ""))
            if xs_fb(mass):
                h.Scale(1000. / xs_fb(mass))  # some xs_fb --> 1 pb
            else:
                print proc, mass, "xs not found"

        outFile.cd(outDir)
        h.Write()

    outFile.Close()


def mu():
    stems = ["ZprimeToTauTau_M_%d" % i for i in [500, 1000, 1500, 2000, 2500, 3000]]
    stems += ["Data", "Diboson", "QCD", "TTBar", "WJets", "ZJets"]
    d = "Fitter/"
    hName = "DiJetMass"
    merge(stems=stems, hName=hName, inDir=d, outDir="muTau_inclusive", suffix="_muTauSR_ForFitter.root", tag="mt")


def had():
    stems = ["ZprimeToTauTau_M_%d" % i for i in [500, 1000, 1500, 2000, 2500, 3000]]
    stems += ["Data", "Diboson", "QCD", "TTBar", "WJets", "ZJets"]
    d = "Fitter/"
    hName = "DiJetMass"
    merge(stems=stems, hName=hName, inDir=d, outDir="tauTau_inclusive", suffix="_diTauSR_ForFitter.root", tag="tt")


def to_h(prefix=""):
    stems = ["%s_ZPrime_%d" % (prefix, i) for i in [500, 1000, 1500, 2000, 2500, 3000]]
    stems += ["%s_VV" % prefix, "%s_QCD" % prefix, "%s_TT" % prefix, "%s_W" % prefix, "%s_Z" % prefix, "%s_data_obs" % prefix]
    d = "Fitter/%s/" % prefix
    hName = "m_effective"
    merge(stems=stems, hName=hName, inDir=d, outDir="%s_inclusive" % prefix, suffix=".root", tag={"eleTau": "et", "emu": "em"}[prefix], dest=".", scale_signal_to_pb=True)


if __name__ == "__main__":
    # m1("eleTau")
    # m1("emu")
    # m2()
    mu()
    had()
    # to_h("eleTau")
    # to_h("emu")

#!/usr/bin/env python

import os
import sys
from root_dest import root_dest


def opts():
    import optparse
    parser = optparse.OptionParser()

    parser.add_option("--masses",
                      dest="masses",
                      default="260 300 350",
                      help="list of masses",
                      )

    parser.add_option("--categories",
                      dest="categories",
                      default="1 2",
                      help="list of categories",
                      )

    parser.add_option("--cards0",
                      dest="cards0",
                      default=False,
                      action="store_true",
                      help="remove and recreate data cards (old method)")

    parser.add_option("--cards",
                      dest="cards",
                      default=False,
                      action="store_true",
                      help="remove and recreate data cards")

    parser.add_option("--fits",
                      dest="fits",
                      default=False,
                      action="store_true",
                      help="do fits/limits")

    parser.add_option("--plots",
                      dest="plots",
                      default=False,
                      action="store_true",
                      help="make plots")

    parser.add_option("--postfit",
                      dest="postfit",
                      default=False,
                      action="store_true",
                      help="make post-fit plots")

    parser.add_option("--postfitonlyone",
                      dest="postfitonlyone",
                      default=False,
                      action="store_true",
                      help="make post-fit plots only at first mass point")

    parser.add_option("--alsoObs",
                      dest="alsoObs",
                      default=False,
                      action="store_true",
                      help="plot observed limit")

    parser.add_option("--full",
                      dest="full",
                      default=False,
                      action="store_true",
                      help="--cards --fits --plots --postfit")

    parser.add_option("--file",
                      dest="file",
                      default="",
                      metavar="x.root",
                      help=" required!!")

    parser.add_option("--BDT",
                      dest="BDT",
                      default=False,
                      action="store_true",
                      help="move limit results to LIMITS-tmp")

    options, args = parser.parse_args()
    if not options.file:
        print "--file is required."
        sys.exit(1)

    file2 = os.path.expanduser(options.file)
    if not os.path.exists(file2):
        print "--file is required to exist (%s does not)." % file2
        sys.exit(1)

    if options.full:
        for item in ["cards", "fits", "plots", "postfit"]:
            setattr(options, item, True)

    return options 


def copy(src="", dest="", link=False):
    try:
        os.remove(dest)
    except OSError as e:
        if e.errno != 2:
            print e
            sys.exit(1)
    if link:
        os.system("ln -s %s %s" % (src, dest))
    else:
        os.system("cp -p %s %s" % (src, dest))


if __name__ == "__main__":
    # rl.txt
    # https://twiki.cern.ch/twiki/bin/viewauth/CMS/SWGuideHiggs2TauLimits
    options = opts()

    masses = options.masses.split()

    cmssw_src = "%s/src" % os.environ["CMSSW_BASE"]
    base = "%s/HiggsAnalysis/HiggsToTauTau" % cmssw_src
    label = "v1"
    lim = "%s/LIMITS%s/bbb/" % (cmssw_src, label)
    inDir = "%s/setup-Hhh" % base

    if options.cards0:
        # # remove and create file and link
        # fName = "htt_tt.inputs-Hhh-8TeV.root"
        # loc = "%s/%s" % (root_dest, fName)
        # copy(src=os.path.abspath(options.file), dest=loc, link=False)
        # copy(src=loc, dest="%s/tt/%s" % (inDir, fName), link=True)

        dc = "%s/dc" % cmssw_src
        common = "--channels=tt --Hhh-categories-tt='%s' --periods=8TeV %s" % (options.categories, options.masses)

        os.system("rm -rf %s" % dc)
        cmd = " ".join(["setup-datacards.py",
                        "--in=%s" % inDir,
                        "--out="+dc,
                        "--analysis=Hhh",
                        common,
                        ])
        # print cmd
        os.system(cmd)
        if options.BDT:
            tmp = "%s/LIMITS-tmp/tt" % cmssw_src
            os.system("mkdir -p %s/" % tmp)
            os.system("cp -rf %s/tt/* %s/" % (lim, tmp))
        os.system("rm -rf %s" % lim)
        os.system("mkdir -p %s" % lim)
        os.system(" ".join(["setup-Hhh.py",
                            "--in=%s" % dc,
                            "--out=%s" % lim,
                            common,
                            ]))

    if options.cards:
        old = "%s/data/limits.config-Hhh" % base
        new = old + "2"
        s1 = "sed s@'tt = Italians'@'tt = Brown'@"
        s2 = "sed s@'channels = et mt tt'@'channels = tt'@"
        os.system("cat %s | %s | %s > %s" % (old, s1, s2, new))

        args = "--update-all --config=%s" % new
        #args += " -a plain"
        args += " -a bbb --new-merging --new-merging-threshold 0.5"
        cmd = "python %s/scripts/doHTohh.py --label='%s' %s" % (base, label, args)
        os.system("cd %s && %s" % (cmssw_src, cmd))


    if options.fits:
        for mass in masses:
            lim1 = "%s/tt/%s" % (lim, mass)
            lopts = ["", " --stable --rMin -5 --rMax 5"][0]
            os.system("limit.py --max-likelihood %s %s" % (lopts, lim1))
            os.system("cat %s/out/mlfit.txt" % lim1)
            #os.system("limit.py --significance-frequentist %s" % lim1)
            #os.system("limit.py --pvalue-frequentist %s" % lim1)
            os.system("limit.py --asymptotic %s" % lim1)

    if options.plots:
        layouts = "%s/python/layouts" % base
        plotcommon = "%s/tt/ masspoints='%s'" % (lim, " ".join(masses))
        if options.BDT and masses == ['350']:
            plotcommon = "%s/ masspoints='%s'" % (tmp, "260 270 280 290 300 310 320 330 340 350")

        os.system(" ".join(["plot",
                            "--max-likelihood",
                            "%s/max-likelihood_sm.py" % layouts,
                            plotcommon,
                            ]))

        os.system(" ".join(["plot",
                            "--asymptotic",
                            "%s/limit-mssm-ggHTohh.py" % layouts,
                            plotcommon,
                            "" if options.alsoObs else "expectedOnly=True",
                            ]))

        #os.system(" ".join(["plot",
        #                    "--significance-frequentist",
        #                    "%s/significance-sm.py" % layouts,
        #                    plotcommon,
        #                    ]))
        #
        #os.system(" ".join(["plot",
        #                    "--pvalue-frequentist",
        #                    "%s/pvalue-sm.py" % layouts,
        #                    plotcommon,
        #                    ]))

    if options.postfit:
        masses = []; print "FIXME: repair postfit"
        for mass in (masses[:1] if options.postfitonlyone else masses):
            lim1 = "%s/tt/%s" % (lim, mass)
            test = "%s/test" % base
            ugh = "-a Hhh --mA 300 --tanb 2"

            os.system("cd %s && python mlfit_and_copy.py %s --skip %s" % (test, ugh, lim1))

            config = "%s/hlim/limits.config-sm-tt-only" % base
            os.system("cd %s && python produce_macros_Hhh.py %s --config %s" % (test, ugh, config))
            os.system("cd %s && ./fixmacros.sh" % test)
            os.system("cd %s && python run_macros.py -a Hhh --config %s" % (test, config))

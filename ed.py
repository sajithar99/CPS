#!/usr/bin/python


import sys

from pykota.tool import Percent, CPSTool, CPSCommandLineError, crashed, N_
from pykota.storage import StorageUserPQuota, StorageGroupPQuota

__doc__ = N_("""edpykota """) 
        
class EdPyKota(CPSTool) :        
    """A class for edpykota."""
    def modifyPQEntry(self, pqkey, pqentry, noquota, softlimit, hardlimit, increase, reset, hardreset, suffix, used) :
        """Modifies a print quota entry."""
        if noquota or ((softlimit is not None) and (hardlimit is not None)) :
            pqentry.setLimits(softlimit, hardlimit)
        if increase :
            newsoft = (pqentry.SoftLimit or 0) + increase         
            newhard = (pqentry.HardLimit or 0) + increase         
            if (newsoft >= 0) and (newhard >= 0) :
                pqentry.setLimits(newsoft, newhard)
            else :    
                self.printInfo(_("You can't set negative limits for %s") % pqkey, "error")
        if reset :
            pqentry.reset()
        if hardreset :    
            pqentry.hardreset()
        if suffix == "User" :
            if used :
                pqentry.setUsage(used)
    
    def main(self, names, options) :
        """Edit user or group quotas."""
        names = self.sanitizeNames(options, names)
        suffix = (options["groups"] and "Group") or "User"        
        printernames = options["printer"].split(",")
            
        if not options["list"] :
            percent = Percent(self)
            percent.display("%s..." % _("Extracting datas"))
        printers = self.storage.getMatchingPrinters(options["printer"])
        entries = getattr(self.storage, "getMatching%ss" % suffix)(",".join(names))
        if not options["list"] :
            percent.setSize(len(printers) * len(entries))
        
        if options["list"] :
            for printer in printers :
                for entry in entries :
                    pqentry = getattr(self.storage, "get%sPQuota" % suffix)(entry, printer)
                    if pqentry.Exists :
                        print "%s@%s" % (entry.Name, printer.Name)
                        print "    %s" % (_("Page counter : %s") % pqentry.PageCounter)
                        print "    %s" % (_("Lifetime page counter : %s") % pqentry.LifePageCounter)
                        print "    %s" % (_("Soft limit : %s") % pqentry.SoftLimit)
                        print "    %s" % (_("Hard limit : %s") % pqentry.HardLimit)
                        print "    %s" % (_("Date limit : %s") % pqentry.DateLimit)
                        print "    %s (Not supported yet)" % (_("Maximum job size : %s") % ((pqentry.MaxJobSize and (_("%s pages") % pqentry.MaxJobSize)) or _("Unlimited")))
                        if hasattr(pqentry, "WarnCount") :
                            print "    %s" % (_("Warning banners printed : %s") % pqentry.WarnCount)
                        print
        elif options["delete"] :    
            percent.display("\n%s..." % _("Deletion"))
            getattr(self.storage, "deleteMany%sPQuotas" % suffix)(printers, entries)
            percent.display("\n")
        else :
            skipexisting = options["skipexisting"]
            used = options["used"]
            if used :
                used = used.strip()
                try :
                    int(used)
                except ValueError :
                    raise CPSCommandLineError, _("Invalid used value %s.") % used
                    
            increase = options["increase"]
            if increase :
                try :
                    increase = int(increase.strip())
                except ValueError :
                    raise CPSCommandLineError, _("Invalid increase value %s.") % increase
            
            noquota = options["noquota"]
            reset = options["reset"]        
            hardreset = options["hardreset"]
            softlimit = hardlimit = None
            if not noquota :
                if options["softlimit"] :
                    try :
                        softlimit = int(options["softlimit"].strip())
                        if softlimit < 0 :
                            raise ValueError
                    except ValueError :    
                        raise CPSCommandLineError, _("Invalid softlimit value %s.") % options["softlimit"]
                if options["hardlimit"] :
                    try :
                        hardlimit = int(options["hardlimit"].strip())
                        if hardlimit < 0 :
                            raise ValueError
                    except ValueError :    
                        raise CPSCommandLineError, _("Invalid hardlimit value %s.") % options["hardlimit"]
                if (softlimit is not None) and (hardlimit is not None) and (hardlimit < softlimit) :        
                    # error, exchange them
                    self.printInfo(_("Hard limit %i is less than soft limit %i, values will be exchanged.") % (hardlimit, softlimit))
                    (softlimit, hardlimit) = (hardlimit, softlimit)
                if hardlimit is None :    
                    hardlimit = softlimit
                    if hardlimit is not None :
                        self.printInfo(_("Undefined hard limit set to soft limit (%s).") % str(hardlimit))
                if softlimit is None :    
                    softlimit = hardlimit
                    if softlimit is not None :
                        self.printInfo(_("Undefined soft limit set to hard limit (%s).") % str(softlimit))
                        
            self.storage.beginTransaction()            
            try :
                if options["add"] :
                    percent.display("\n%s...\n" % _("Creation"))
                    if not entries :    
                        self.printInfo(_("No entry matches %s. Please use pkusers to create them first.") % (" ".join(names)), "warn")
                            
                    factory = globals()["Storage%sPQuota" % suffix]
                    for printer in printers :
                        pname = printer.Name
                        for entry in entries :
                            ename = entry.Name
                            pqkey = "%s@%s" % (ename, pname)
                            pqentry = factory(self.storage, entry, printer)
                            self.modifyPQEntry(pqkey, pqentry, noquota, \
                                                        softlimit, hardlimit, \
                                                        increase, reset, \
                                                        hardreset, suffix, used)
                            oldpqentry = getattr(self.storage, "add%sPQuota" % suffix)(pqentry)
                            if oldpqentry is not None :    
                                if skipexisting :
                                    self.logdebug("%s print quota entry %s@%s already exists, skipping." % (suffix, ename, pname))
                                else :    
                                    self.logdebug("%s print quota entry %s@%s already exists, will be modified." % (suffix, ename, pname))
                                    self.modifyPQEntry(pqkey, oldpqentry, noquota, \
                                                        softlimit, hardlimit, \
                                                        increase, reset, \
                                                        hardreset, suffix, used)
                                    oldpqentry.save()                    
                            percent.oneMore()
                else :        
                    percent.display("\n%s...\n" % _("Modification"))
                    for printer in printers :
                        for entry in entries :
                            pqkey = "%s@%s" % (entry.Name, printer.Name)
                            pqentry = getattr(self.storage, "get%sPQuota" % suffix)(entry, printer)
                            if pqentry.Exists :     
                                self.modifyPQEntry(pqkey, pqentry, noquota, \
                                                    softlimit, hardlimit, \
                                                    increase, reset, \
                                                    hardreset, suffix, used)
                                pqentry.save()        
                            percent.oneMore()
            except :                    
                self.storage.rollbackTransaction()
                raise
            else :    
                self.storage.commitTransaction()
                            
        if not options["list"] :
            percent.done()
            
if __name__ == "__main__" : 
    retcode = 0
    try :
        defaults = { \
                     "printer" : "*", \
                   }
        short_options = "vhdnagrLP:S:H:G:RU:I:s"
        long_options = ["help", "version", \
                        "delete", "list", \
                        "noquota", "add", \
                        "groups", "reset", "hardreset", \
                        "printer=", "softlimit=", "hardlimit=", \
                        "increase=", "used=", "skipexisting"]
        
        # Initializes the command line tool
        manager = EdPyKota(doc=__doc__)
        manager.deferredInit()
        
        # parse and checks the command line
        (options, args) = manager.parseCommandline(sys.argv[1:], short_options, long_options)
        
        # sets long options
        options["help"] = options["h"] or options["help"]
        options["version"] = options["v"] or options["version"]
        options["add"] = options["a"] or options["add"]
        options["groups"] = options["g"] or options["groups"]
        options["printer"] = options["P"] or options["printer"] or defaults["printer"]
        options["softlimit"] = options["S"] or options["softlimit"]
        options["hardlimit"] = options["H"] or options["hardlimit"] 
        options["reset"] = options["r"] or options["reset"] 
        options["noquota"] = options["n"] or options["noquota"]
        options["delete"] = options["d"] or options["delete"] 
        options["hardreset"] = options["R"] or options["hardreset"] 
        options["used"] = options["U"] or options["used"]
        options["increase"] = options["I"] or options["increase"]
        options["list"] = options["L"] or options["list"]
        options["skipexisting"] = options["s"] or options["skipexisting"]
        
        if options["help"] :
            manager.display_usage_and_quit()
        elif options["version"] :
            manager.display_version_and_quit()
        elif (options["add"] and options["delete"]) \
             or (options["noquota"] and (options["hardlimit"] or options["softlimit"])) \
             or (options["groups"] and options["used"]) \
             or (options["skipexisting"] and not options["add"]) :
            raise CPSCommandLineError, _("incompatible options, see help.")
        elif options["delete"] and not args :
            raise CPSCommandLineError, _("You have to pass user or group names on the command line")
        else :
            retcode = manager.main(args, options)
    except KeyboardInterrupt :        
        sys.stderr.write("\nInterrupted with Ctrl+C !\n")
        retcode = -3
    except CPSCommandLineError, msg :     
        sys.stderr.write("%s : %s\n" % (sys.argv[0], msg))
        retcode = -2
    except SystemExit :        
        pass
    except :
        try :
            manager.crashed("edpykota failed")
        except :    
            crashed("edpykota failed")
        retcode = -1

    try :
        manager.storage.close()
    except (TypeError, NameError, AttributeError) :    
        pass
        
    sys.exit(retcode)    

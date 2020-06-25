#!/usr/bin/python


import sys
import os
import pwd

from pykota.tool import CPSTool, CPSCommandLineError, crashed, N_

from pkpgpdls import analyzer, pdlparser
    

__doc__ = N_(""" pykotme """)
        
        
class PyKotMe(CPSTool) :        
    """A class for pykotme."""
    def main(self, files, options) :
        """Gives print quotes."""
        if (not sys.stdin.isatty()) and ("-" not in files) :
            files.append("-")
        totalsize = 0    
        for filename in files :    
            try :
                parser = analyzer.PDLAnalyzer(filename)
                totalsize += parser.getJobSize()
            except (pdlparser.PDLParserError, IOError), msg :    
                self.printInfo(msg)
            
        printers = self.storage.getMatchingPrinters(options["printer"])
        if not printers :
            raise CPSCommandLineError, _("There's no printer matching %s") % options["printer"]
            
        username = pwd.getpwuid(os.getuid())[0]
        user = self.storage.getUser(username)
        if user.Exists and user.LimitBy and (user.LimitBy.lower() == "balance"):
            print _("Your account balance : %.2f") % (user.AccountBalance or 0.0)
            
        print _("Job size : %i pages") % totalsize    
        if user.Exists :
            if user.LimitBy == "noprint" :
                print _("Your account settings forbid you to print at this time.")
            else :    
                for printer in printers :
                    userpquota = self.storage.getUserPQuota(user, printer)
                    if userpquota.Exists :
                        if printer.MaxJobSize and (totalsize > printer.MaxJobSize) :
                            print _("You are not allowed to print so many pages on printer %s at this time.") % printer.Name
                        else :    
                            cost = userpquota.computeJobPrice(totalsize)
                            msg = _("Cost on printer %s : %.2f") % (printer.Name, cost)
                            if printer.PassThrough :
                                msg = "%s (%s)" % (msg, _("won't be charged, printer is in passthrough mode"))
                            elif user.LimitBy == "nochange" :    
                                msg = "%s (%s)" % (msg, _("won't be charged, your account is immutable"))
                            print msg    
            
if __name__ == "__main__" : 
    retcode = 0
    try :
        defaults = { \
                     "printer" : "*", \
                   }
        short_options = "vhP:"
        long_options = ["help", "version", "printer="]
        
        # Initializes the command line tool
        sender = PyKotMe(doc=__doc__)
        sender.deferredInit()
        
        # parse and checks the command line
        (options, args) = sender.parseCommandline(sys.argv[1:], short_options, long_options, allownothing=1)
        
        # sets long options
        options["help"] = options["h"] or options["help"]
        options["version"] = options["v"] or options["version"]
        options["printer"] = options["P"] or options["printer"] or defaults["printer"]
        
        if options["help"] :
            sender.display_usage_and_quit()
        elif options["version"] :
            sender.display_version_and_quit()
        else :
            retcode = sender.main(args, options)
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
            sender.crashed("pykotme failed")
        except :    
            crashed("pykotme failed")
        retcode = -1

    try :
        sender.storage.close()
    except (TypeError, NameError, AttributeError) :    
        pass
        
    sys.exit(retcode)    

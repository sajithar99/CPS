#!/usr/bin/python


import sys
import os
import pwd

from mx import DateTime

from pykota.tool import CPSTool, ToolError, CPSCommandLineError, crashed, N_
from pykota import reporter

__doc__ = N_("""repykota """)
        
class RePyKota(CPSTool) :        
    """A class for repykota."""
    def main(self, ugnames, options) :
        """Print Quota reports generator."""
        if self.config.isAdmin :
            # PyKota administrator
            if not ugnames :
                # no username, means all usernames
                ugnames = [ "*" ]
                
            if options["ingroups"] :
                groupsnames = options["ingroups"].split(",")
                groups = [self.storage.getGroup(gname) for gname in groupsnames]
                members = {}
                for group in groups :
                    if not group.Exists :
                        self.printInfo("Group %s doesn't exist." % group.Name, "warn")
                    else :    
                        for user in self.storage.getGroupMembers(group) :
                            members[user.Name] = user
                ugnames = [ m for m in members.keys() if self.matchString(m, ugnames) ]
        else :        
            # reports only the current user
            if options["ingroups"] :
                raise CPSCommandLineError, _("Option --ingroups is reserved to PyKota Administrators.")
                
            username = pwd.getpwuid(os.geteuid())[0]
            if options["groups"] :
                user = self.storage.getUser(username)
                if user.Exists :
                    ugnames = [ g.Name for g in self.storage.getUserGroups(user) ]
                else :    
                    ugnames = [ ]
            else :
                ugnames = [ username ]
        
        printers = self.storage.getMatchingPrinters(options["printer"])
        if not printers :
            raise CPSCommandLineError, _("There's no printer matching %s") % options["printer"]
            
        self.reportingtool = reporter.openReporter(self, "text", printers, ugnames, (options["groups"] and 1) or 0)    
        print self.reportingtool.generateReport()
                    
if __name__ == "__main__" : 
    retcode = 0
    try :
        defaults = { \
                     "printer" : "*", \
                   }
        short_options = "vhugi:P:"
        long_options = ["help", "version", "users", "groups", "ingroups=", "printer="]
        
        # Initializes the command line tool
        reportTool = RePyKota(doc=__doc__)
        reportTool.deferredInit()
        
        # parse and checks the command line
        (options, args) = reportTool.parseCommandline(sys.argv[1:], short_options, long_options, allownothing=1)
        
        # sets long options
        options["help"] = options["h"] or options["help"]
        options["version"] = options["v"] or options["version"]
        options["users"] = options["u"] or options["users"]
        options["groups"] = options["g"] or options["groups"]
        options["printer"] = options["P"] or options["printer"] or defaults["printer"]
        options["ingroups"] = options["i"] or options["ingroups"]
        
        if options["help"] :
            reportTool.display_usage_and_quit()
        elif options["version"] :
            reportTool.display_version_and_quit()
        elif (options["users"] or options["ingroups"]) and options["groups"] :
            raise CPSCommandLineError, _("incompatible options, see help.")
        else :
            retcode = reportTool.main(args, options)
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
            reportTool.crashed("repykota failed")
        except :    
            crashed("repykota failed")
        retcode = -1

    try :
        reportTool.storage.close()
    except (TypeError, NameError, AttributeError) :    
        pass
        
    sys.exit(retcode)    

#!/usr/bin/python


import os
import sys
import pwd

from pykota.tool import Percent, CPSTool, CPSCommandLineError, crashed, N_
from pykota.storage import StoragePrinter

from pkipplib import pkipplib

__doc__ = N_(""" pkprinters """)
        
class PKPrinters(CPSTool) :        
    """A class for a printers manager."""
    def modifyPrinter(self, printer, charges, perpage, perjob, description, passthrough, nopassthrough, maxjobsize) :
        if charges :
            printer.setPrices(perpage, perjob)    
        if description is not None :        # NB : "" is allowed !
            printer.setDescription(description)
        if nopassthrough :    
            printer.setPassThrough(False)
        if passthrough :    
            printer.setPassThrough(True)
        if maxjobsize is not None :
            printer.setMaxJobSize(maxjobsize)
            
    def managePrintersGroups(self, pgroups, printer, remove) :        
        """Manage printer group membership."""
        for pgroup in pgroups :
            if remove :
                pgroup.delPrinterFromGroup(printer)
            else :
                pgroup.addPrinterToGroup(printer)    
                
    def getPrinterDeviceURI(self, printername) :            
        """Returns the Device URI attribute for a particular printer."""
        if not printername :
            return ""
        cups = pkipplib.CUPS()
        req = cups.newRequest(pkipplib.IPP_GET_PRINTER_ATTRIBUTES)
        req.operation["printer-uri"] = ("uri", cups.identifierToURI("printers", printername))
        try :
            return cups.doRequest(req).printer["device-uri"][0][1]
        except :    
            return ""
        
    def isPrinterCaptured(self, printername=None, deviceuri=None) :
        """Returns True if the printer is already redirected through PyKota's backend, else False."""
        if (deviceuri or self.getPrinterDeviceURI(printername)).find("cupspykota:") != -1 :
            return True
        else :    
            return False
        
    def reroutePrinterThroughPyKota(self, printer) :    
        """Reroutes a CUPS printer through PyKota."""
        uri = self.getPrinterDeviceURI(printer.Name)
        if uri and (not self.isPrinterCaptured(deviceuri=uri)) :
             newuri = "cupspykota://%s" % uri
             self.regainPriv() # to avoid having to enter password.
             os.system('lpadmin -p "%s" -v "%s"' % (printer.Name, newuri))
             self.logdebug("Printer %s rerouted to %s" % (printer.Name, newuri))
             self.dropPriv()
             
    def deroutePrinterFromPyKota(self, printer) :    
        """Deroutes a PyKota printer through CUPS only."""
        uri = self.getPrinterDeviceURI(printer.Name)
        if uri and self.isPrinterCaptured(deviceuri=uri) :
             newuri = uri.replace("cupspykota:", "")
             if newuri.startswith("//") :
                 newuri = newuri[2:]
             self.regainPriv() # to avoid having to enter password.
             os.system('lpadmin -p "%s" -v "%s"' % (printer.Name, newuri))
             self.logdebug("Printer %s rerouted to %s" % (printer.Name, newuri))
             self.dropPriv()    
                                     
    def main(self, names, options) :
        """Manage printers."""
        if (not self.config.isAdmin) and (not options["list"]) :
            raise CPSCommandLineError, "%s : %s" % (pwd.getpwuid(os.geteuid())[0], _("You're not allowed to use this command."))
            
        docups = options["cups"]
        
        if not options["list"] :    
            percent = Percent(self)
            
        if not options["add"] :
            if not options["list"] :
                percent.display("%s..." % _("Extracting datas"))
            if not names :      # NB : can't happen for --delete because it's catched earlier
                names = ["*"]
            printers = self.storage.getMatchingPrinters(",".join(names))
            if not printers :
                if not options["list"] :
                    percent.display("\n")
                raise CPSCommandLineError, _("There's no printer matching %s") % " ".join(names)
            if not options["list"] :    
                percent.setSize(len(printers))
                
        if options["list"] :
            for printer in printers :
                parents = ", ".join([p.Name for p in self.storage.getParentPrinters(printer)])
                print "%s [%s] (%s + #*%s)" % \
                      (printer.Name, printer.Description, printer.PricePerJob, \
                       printer.PricePerPage)
                print "    %s" % (_("Passthrough mode : %s") % ((printer.PassThrough and _("ON")) or _("OFF")))
                print "    %s" % (_("Maximum job size : %s") % ((printer.MaxJobSize and (_("%s pages") % printer.MaxJobSize)) or _("Unlimited")))
                print "    %s" % (_("Routed through PyKota : %s") % ((self.isPrinterCaptured(printer.Name) and _("YES")) or _("NO")))
                if parents : 
                    print "    %s %s" % (_("in"), parents)
                print    
        elif options["delete"] :    
            percent.display("\n%s..." % _("Deletion"))
            self.storage.deleteManyPrinters(printers)
            percent.display("\n")
            if docups :
                percent.display("%s...\n" % _("Rerouting printers to CUPS"))
                for printer in printers :
                    self.deroutePrinterFromPyKota(printer)
                    percent.oneMore()
        else :
            if options["groups"] :        
                printersgroups = self.storage.getMatchingPrinters(options["groups"])
                if not printersgroups :
                    raise CPSCommandLineError, _("There's no printer matching %s") % " ".join(options["groups"].split(','))
            else :         
                printersgroups = []
                    
            if options["charge"] :
                try :
                    charges = [float(part) for part in options["charge"].split(',', 1)]
                except ValueError :    
                    raise CPSCommandLineError, _("Invalid charge amount value %s") % options["charge"]
                else :    
                    if len(charges) > 2 :
                        charges = charges[:2]
                    if len(charges) != 2 :
                        charges = [charges[0], None]
                    (perpage, perjob) = charges
            else :        
                charges = perpage = perjob = None
                    
            if options["maxjobsize"] :        
                try :
                    maxjobsize = int(options["maxjobsize"])
                    if maxjobsize < 0 :
                        raise ValueError
                except ValueError :    
                    raise CPSCommandLineError, _("Invalid maximum job size value %s") % options["maxjobsize"]
            else :        
                maxjobsize = None
                    
            description = options["description"]
            if description :
                description = description.strip()
                
            nopassthrough = options["nopassthrough"]    
            passthrough = options["passthrough"]
            remove = options["remove"]
            skipexisting = options["skipexisting"]
            self.storage.beginTransaction()
            try :
                if options["add"] :    
                    percent.display("%s...\n" % _("Creation"))
                    percent.setSize(len(names))
                    for pname in names :
                        if self.isValidName(pname) :
                            printer = StoragePrinter(self.storage, pname)
                            self.modifyPrinter(printer, charges, perpage, perjob, \
                                           description, passthrough, \
                                           nopassthrough, maxjobsize)
                            oldprinter = self.storage.addPrinter(printer)               
                            
                            if docups :
                                 self.reroutePrinterThroughPyKota(printer)
                                     
                            if oldprinter is not None :
                                if skipexisting :
                                    self.logdebug(_("Printer %s already exists, skipping.") % pname)
                                else :    
                                    self.logdebug(_("Printer %s already exists, will be modified.") % pname)
                                    self.modifyPrinter(oldprinter, charges, \
                                               perpage, perjob, description, \
                                               passthrough, nopassthrough, \
                                               maxjobsize)
                                    oldprinter.save()           
                                    self.managePrintersGroups(printersgroups, oldprinter, remove)
                            elif printersgroups :        
                                self.managePrintersGroups(printersgroups, \
                                                          self.storage.getPrinter(pname), \
                                                          remove)
                        else :    
                            raise CPSCommandLineError, _("Invalid printer name %s") % pname
                        percent.oneMore()
                else :        
                    percent.display("\n%s...\n" % _("Modification"))
                    for printer in printers :        
                        self.modifyPrinter(printer, charges, perpage, perjob, \
                                           description, passthrough, \
                                           nopassthrough, maxjobsize)
                        printer.save()    
                        self.managePrintersGroups(printersgroups, printer, remove)
                        if docups :
                            self.reroutePrinterThroughPyKota(printer)
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
        short_options = "hvaCc:D:dg:lrsnpm:"
        long_options = ["help", "version", "add", "cups", "charge=", "description=", \
                        "delete", "groups=", "list", "remove", \
                        "skipexisting", "passthrough", "nopassthrough", \
                        "maxjobsize="]
        
        # Initializes the command line tool
        manager = PKPrinters(doc=__doc__)
        manager.deferredInit()
        
        # parse and checks the command line
        (options, args) = manager.parseCommandline(sys.argv[1:], short_options, long_options)
        
        # sets long options
        options["help"] = options["h"] or options["help"]
        options["version"] = options["v"] or options["version"]
        options["add"] = options["a"] or options["add"]
        options["cups"] = options["C"] or options["cups"]
        options["charge"] = options["c"] or options["charge"]
        options["description"] = options["D"] or options["description"]
        options["delete"] = options["d"] or options["delete"] 
        options["groups"] = options["g"] or options["groups"]
        options["list"] = options["l"] or options["list"]
        options["remove"] = options["r"] or options["remove"]
        options["skipexisting"] = options["s"] or options["skipexisting"]
        options["maxjobsize"] = options["m"] or options["maxjobsize"]
        options["passthrough"] = options["p"] or options["passthrough"]
        options["nopassthrough"] = options["n"] or options["nopassthrough"]
        
        if options["help"] :
            manager.display_usage_and_quit()
        elif options["version"] :
            manager.display_version_and_quit()
        elif (options["delete"] and (options["add"] or options["groups"] or options["charge"] or options["remove"] or options["description"])) \
           or (options["skipexisting"] and not options["add"]) \
           or (options["list"] and (options["add"] or options["delete"] or options["groups"] or options["charge"] or options["remove"] or options["description"])) \
           or (options["passthrough"] and options["nopassthrough"]) \
           or (options["remove"] and options["add"]) :
            raise CPSCommandLineError, _("incompatible options, see help.")
        elif options["remove"] and not options["groups"] :
            raise CPSCommandLineError, _("You have to pass printer groups names on the command line")
        elif (not args) and (options["add"] or options["delete"]) :
            raise CPSCommandLineError, _("You have to pass printer names on the command line")
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
            manager.crashed("pkprinters failed")
        except :    
            crashed("pkprinters failed")
        retcode = -1

    try :
        manager.storage.close()
    except (TypeError, NameError, AttributeError) :    
        pass
        
    sys.exit(retcode)    

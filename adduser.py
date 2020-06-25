#!/usr/bin/python


import sys
import pwd
import grp

from pykota.tool import Percent, CPSTool, CPSCommandLineError, crashed, N_
from pykota.storage import StorageUser, StorageGroup

__doc__ = N_(""" adduser """)        
class Adduser(CPSTool) :        
    """A class for a users and users groups manager."""
    def modifyEntry(self, entry, groups, limitby, description, overcharge=None, balance=None, balancevalue=None, comment=None, email=None) :
        """Modifies an entry."""
        if description is not None : # NB : "" is allowed !
            entry.setDescription(description)
        if limitby :    
            entry.setLimitBy(limitby)
        if not groups :
            if email is not None :      # we allow "" to empty the field
                if email.startswith("@") :
                    email = "%s%s" % (entry.Name, email)
                if email and email.count('@') != 1 :
                    raise CPSCommandLineError, _("Invalid email address %s") % email
                entry.setEmail(email)
            if overcharge is not None : # NB : 0 is allowed !     
                entry.setOverChargeFactor(overcharge)
            if balance :
                if balance.startswith("+") or balance.startswith("-") :
                    newbalance = float(entry.AccountBalance or 0.0) + balancevalue
                    newlifetimepaid = float(entry.LifeTimePaid or 0.0) + balancevalue
                    entry.setAccountBalance(newbalance, newlifetimepaid, comment)
                else :
                    diff = balancevalue - float(entry.AccountBalance or 0.0)
                    newlifetimepaid = float(entry.LifeTimePaid or 0.0) + diff
                    entry.setAccountBalance(balancevalue, newlifetimepaid, comment)
                    
    def manageUsersGroups(self, ugroups, user, remove) :        
        """Manage user group membership."""
        for ugroup in ugroups :
            if remove :
                ugroup.delUserFromGroup(user)
            else :
                ugroup.addUserToGroup(user)
                
    def main(self, names, options) :
        """Manage users or groups."""
        names = self.sanitizeNames(options, names)
        suffix = (options["groups"] and "Group") or "User"        
        
        if not options["list"] :
            percent = Percent(self)
            
        if not options["add"] :
            if not options["list"] :
                percent.display("%s..." % _("Extracting datas"))
            if not names :      # NB : can't happen for --delete because it's catched earlier
                names = ["*"]
            entries = getattr(self.storage, "getMatching%ss" % suffix)(",".join(names))
            if not entries :
                if not options["list"] :
                    percent.display("\n")
                raise CPSCommandLineError, _("There's no %s matching %s") % (_(suffix.lower()), " ".join(names))
            if not options["list"] :    
                percent.setSize(len(entries))
                
        if options["list"] :
            if suffix == "User" :
                maildomain = self.config.getMailDomain()
                smtpserver = self.config.getSMTPServer()
                for entry in entries :
                    email = entry.Email
                    if not email :
                        if maildomain :     
                            email = "%s@%s" % (entry.Name, maildomain)
                        elif smtpserver :    
                            email = "%s@%s" % (entry.Name, smtpserver)
                        else :    
                            email = "%s@%s" % (entry.Name, "localhost")
                    msg = "%s - <%s>" % (entry.Name, email)
                    if entry.Description :
                        msg += " - %s" % entry.Description
                    print msg    
                    print "    %s" % (_("Limited by : %s") % entry.LimitBy)
                    print "    %s" % (_("Account balance : %.2f") % (entry.AccountBalance or 0.0))
                    print "    %s" % (_("Total paid so far : %.2f") % (entry.LifeTimePaid or 0.0))
                    print "    %s" % (_("Overcharging factor : %.2f") % entry.OverCharge)
                    print
            else :    
                for entry in entries :
                    msg = "%s" % entry.Name
                    if entry.Description :
                        msg += " - %s" % entry.Description
                    print msg    
                    print "    %s" % (_("Limited by : %s") % entry.LimitBy)
                    print "    %s" % (_("Group balance : %.2f") % (entry.AccountBalance or 0.0))
                    print "    %s" % (_("Total paid so far : %.2f") % (entry.LifeTimePaid or 0.0))
                    print
        elif options["delete"] :    
            percent.display("\n%s..." % _("Deletion"))
            getattr(self.storage, "deleteMany%ss" % suffix)(entries)
            percent.display("\n")
        else :
            limitby = options["limitby"]
            if limitby :
                limitby = limitby.strip().lower()
            if limitby :
                if limitby not in ('quota', 'balance', 'noquota', \
                                            'noprint', 'nochange') :
                    raise CPSCommandLineError, _("Invalid limitby value %s") % options["limitby"]
                if (limitby in ('nochange', 'noprint')) and options["groups"] :    
                    raise CPSCommandLineError, _("Invalid limitby value %s") % options["limitby"]
                
            overcharge = options["overcharge"]
            if overcharge :
                try :
                    overcharge = float(overcharge.strip())
                except (ValueError, AttributeError) :    
                    raise CPSCommandLineError, _("Invalid overcharge value %s") % options["overcharge"]
                    
            balance = options["balance"]
            if balance :
                balance = balance.strip()
                try :
                    balancevalue = float(balance)
                except ValueError :    
                    raise CPSCommandLineError, _("Invalid balance value %s") % options["balance"]
            else :    
                balancevalue = None
                
            if options["ingroups"] :
                usersgroups = self.storage.getMatchingGroups(options["ingroups"])
                if not usersgroups :
                    raise CPSCommandLineError, _("There's no users group matching %s") % " ".join(options["ingroups"].split(','))
            else :         
                usersgroups = []
                    
            description = options["description"]
            if description :
                description = description.strip()
                
            comment = options["comment"]
            if comment :
                comment = comment.strip()
            email = options["email"]    
            if email :
                email = email.strip()
            skipexisting = options["skipexisting"]    
            groups = options["groups"]
            remove = options["remove"]
            self.storage.beginTransaction()
            try :    
                if options["add"] :    
                    rejectunknown = self.config.getRejectUnknown()    
                    percent.display("%s...\n" % _("Creation"))
                    percent.setSize(len(names))
                    for ename in names :
                        useremail = None
                        if not groups :
                            splitname = ename.split('/', 1)     # username/email
                            if len(splitname) == 1 :
                                splitname.append("")
                            (ename, useremail) = splitname
                        if self.isValidName(ename) :
                            reject = 0
                            if rejectunknown :
                                if groups :
                                    try :
                                        grp.getgrnam(ename)
                                    except KeyError :    
                                        self.printInfo(_("Unknown group %s") % ename, "error")
                                        reject = 1
                                else :    
                                    try :
                                        pwd.getpwnam(ename)
                                    except KeyError :    
                                        self.printInfo(_("Unknown user %s") % ename, "error")
                                        reject = 1
                            if not reject :        
                                entry = globals()["Storage%s" % suffix](self.storage, ename)
                                if groups :
                                    self.modifyEntry(entry, groups, limitby, \
                                                     description)
                                else :    
                                    self.modifyEntry(entry, groups, limitby, \
                                                     description, overcharge,\
                                                     balance, balancevalue, \
                                                     comment, useremail or email)
                                oldentry = getattr(self.storage, "add%s" % suffix)(entry)
                                if oldentry is not None :
                                    if skipexisting :
                                        self.logdebug(_("%s %s already exists, skipping.") % (_(suffix), ename))
                                    else :    
                                        self.logdebug(_("%s %s already exists, will be modified.") % (_(suffix), ename))
                                        if groups :
                                            self.modifyEntry(oldentry, groups, \
                                                     limitby, description)
                                        else :
                                            self.modifyEntry(oldentry, groups, limitby, \
                                                     description, overcharge,\
                                                     balance, balancevalue, \
                                                     comment, useremail or email)
                                        oldentry.save()
                                        if not groups :
                                            self.manageUsersGroups(usersgroups, oldentry, remove)
                                elif usersgroups and not groups :
                                    self.manageUsersGroups(usersgroups, \
                                                           self.storage.getUser(ename), \
                                                           remove)
                        else :
                            raise CPSCommandLineError, _("Invalid name %s") % ename
                        percent.oneMore()
                else :
                    percent.display("\n%s...\n" % _("Modification"))
                    for entry in entries :
                        if groups :
                            self.modifyEntry(entry, groups, limitby, description)
                        else :    
                            self.modifyEntry(entry, groups, limitby, description, \
                                             overcharge, balance, balancevalue, \
                                             comment, email)
                            self.manageUsersGroups(usersgroups, entry, remove)                
                        entry.save()    
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
                     "comment" : "", \
                   }
        short_options = "hvaD:dgl:rso:i:b:C:Le:"
        long_options = ["help", "version", "add", "description=", \
                        "delete", "groups", "list", "remove", \
                        "skipexisting", "overcharge=", "email=", \
                        "ingroups=", "limitby=", "balance=", "comment=", \
                       ]
                        
        
        # Initializes the command line tool
        manager = Adduser(doc=__doc__)
        manager.deferredInit()
        
        # parse and checks the command line
        (options, args) = manager.parseCommandline(sys.argv[1:], short_options, long_options)
        
        # sets long options
        options["help"] = options["h"] or options["help"]
        options["version"] = options["v"] or options["version"]
        options["add"] = options["a"] or options["add"]
        options["description"] = options["D"] or options["description"]
        options["delete"] = options["d"] or options["delete"] 
        options["groups"] = options["g"] or options["groups"]
        options["list"] = options["L"] or options["list"]
        options["remove"] = options["r"] or options["remove"]
        options["skipexisting"] = options["s"] or options["skipexisting"]
        options["limitby"] = options["l"] or options["limitby"]
        options["balance"] = options["b"] or options["balance"] 
        options["ingroups"] = options["i"] or options["ingroups"]
        options["overcharge"] = options["o"] or options["overcharge"]
        options["comment"] = options["C"] or options["comment"] or defaults["comment"]
        options["email"] = options["e"] or options["email"]
        
        if options["help"] :
            manager.display_usage_and_quit()
        elif options["version"] :
            manager.display_version_and_quit()
        elif (options["delete"] and (options["add"] or options["remove"] or options["description"] or options["email"])) \
           or (options["skipexisting"] and not options["add"]) \
           or (options["list"] and (options["add"] or options["delete"] or options["remove"] or options["description"] or options["email"])) \
           or (options["groups"] and (options["balance"] or options["ingroups"] or options["overcharge"])) :
            raise CPSCommandLineError, _("incompatible options, see help.")
        elif options["remove"] and not options["ingroups"] :    
            raise CPSCommandLineError, _("You have to pass user groups names on the command line")
        elif (not args) and (options["add"] or options["delete"]) :
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
            manager.crashed("pkusers failed")
        except :    
            crashed("pkusers failed")
        retcode = -1

    try :
        manager.storage.close()
    except (TypeError, NameError, AttributeError) :    
        pass
        
    sys.exit(retcode)    

import sys
import os
import time
import shutil
import subprocess
import traceback
import django
import socket
from django.utils.translation import ugettext as _
from django.contrib import messages
import forms
import models
import viewlib
import botslib
import pluglib
import botsglobal
import py2html
from botsconfig import *

def server_error(request, template_name='500.html'):
    ''' the 500 error handler.
        Templates: `500.html`
        Context: None
        str().decode(): bytes->unicode
    '''
    exc_info = traceback.format_exc(None).decode('utf-8','ignore')
    botsglobal.logger.info(_(u'Ran into server error: "%(error)s"'),{'error':str(exc_info)})
    temp = django.template.loader.get_template(template_name)  #You need to create a 500.html template.
    return django.http.HttpResponseServerError(temp.render(django.template.Context({'exc_info':exc_info})))

def index(request,*kw,**kwargs):
    return django.shortcuts.render_to_response('admin/base.html', {},context_instance=django.template.RequestContext(request))

def home(request,*kw,**kwargs):
    return django.shortcuts.render_to_response('bots/about.html', {'botsinfo':botslib.botsinfo()},context_instance=django.template.RequestContext(request))

def reports(request,*kw,**kwargs):
    #~ print 'reports received',kw,kwargs,request.POST,request.GET
    if request.method == 'GET':
        if 'select' in request.GET:             #via menu, go to select form
            formout = forms.SelectReports()
            return viewlib.render(request,formout)
        else:                              #via menu, parse get-parameters, go to view form
            cleaned_data = {'page':1,'sortedby':'idta','sortedasc':False}
    else:                                  # request.method == 'POST'
        if 'fromselect' in request.POST:        #coming from select criteria screen
            formin = forms.SelectReports(request.POST)
            if not formin.is_valid():
                return viewlib.render(request,formin)
        else:
            formin = forms.ViewReports(request.POST)
            if not formin.is_valid():
                return viewlib.render(request,formin)
            if '2select' in request.POST:         #coming from ViewIncoming, change the selection criteria, go to select form
                formout = forms.SelectReports(formin.cleaned_data)
                return viewlib.render(request,formout)
            elif 'report2incoming' in request.POST:         #coming from ViewIncoming, go to incoming
                request.POST = viewlib.preparereport2view(request.POST,int(request.POST['report2incoming']))
                return incoming(request)
            elif 'report2outgoing' in request.POST:         #coming from ViewIncoming, go to incoming
                request.POST = viewlib.preparereport2view(request.POST,int(request.POST['report2outgoing']))
                return outgoing(request)
            elif 'report2process' in request.POST:         #coming from ViewIncoming, go to incoming
                request.POST = viewlib.preparereport2view(request.POST,int(request.POST['report2process']))
                return process(request)
            elif 'report2errors' in request.POST:         #coming from ViewIncoming, go to incoming
                newpost = viewlib.preparereport2view(request.POST,int(request.POST['report2errors']))
                newpost['statust'] = ERROR
                request.POST = newpost
                return incoming(request)
            else:                                    #coming from ViewIncoming
                viewlib.handlepagination(request.POST,formin.cleaned_data)
        cleaned_data = formin.cleaned_data

    query = models.report.objects.all()
    pquery = viewlib.filterquery(query,cleaned_data)
    formout = forms.ViewReports(initial=cleaned_data)
    return viewlib.render(request,formout,pquery)

def incoming(request,*kw,**kwargs):
    if request.method == 'GET':
        if 'select' in request.GET:             #via menu, go to select form
            formout = forms.SelectIncoming()
            return viewlib.render(request,formout)
        else:                                   #via menu, parse recevied parameters
            cleaned_data = {'page':1,'sortedby':'idta','sortedasc':False,'lastrun':bool(int(request.GET.get('lastrun',0)))}
    else:                                  # request.method == 'POST'
        if '2outgoing' in request.POST:        #coming from ViewIncoming, go to outgoing form using same criteria
            request.POST = viewlib.changepostparameters(request.POST,soort='in2out')
            return outgoing(request)
        elif '2process' in request.POST:        #coming from ViewIncoming, go to outgoing form using same criteria
            request.POST = viewlib.changepostparameters(request.POST,soort='2process')
            return process(request)
        elif '2confirm' in request.POST:        #coming from ViewIncoming, go to outgoing form using same criteria
            request.POST = viewlib.changepostparameters(request.POST,soort='in2confirm')
            return process(request)
        elif 'fromselect' in request.POST:        #coming from select criteria screen
            formin = forms.SelectIncoming(request.POST)
            if not formin.is_valid():
                return viewlib.render(request,formin)
        else:                                   #coming from ViewIncoming
            formin = forms.ViewIncoming(request.POST)
            if not formin.is_valid():
                return viewlib.render(request,formin)
            elif '2select' in request.POST:         #go to select form using same criteria
                formout = forms.SelectIncoming(formin.cleaned_data)
                return viewlib.render(request,formout)
            elif 'delete' in request.POST:        #coming from ViewIncoming
                idta = int(request.POST[u'delete'])
                #~ query = models.filereport.objects.filter(idta=int(idta)).all().delete()
                models.filereport.objects.filter(idta=idta).delete()
                ta_object = models.ta.objects.get(idta=idta)
                viewlib.gettrace(ta_object)
                viewlib.trace2delete(ta_object)
            elif 'retransmit' in request.POST:
                idta = request.POST[u'retransmit']
                filereport = models.filereport.objects.get(idta=int(idta))
                if filereport.fromchannel:   #for resend files fromchannel has no value. (do not rereceive resend items)
                    filereport.retransmit = not filereport.retransmit
                    filereport.save()
            elif 'rereceiveall' in request.POST:
                #select all objects with parameters and set retransmit
                query = models.filereport.objects.all()
                incomingfiles = viewlib.filterquery2(query,formin.cleaned_data)
                for incomingfile in incomingfiles:   #for resend files fromchannel has no value. (do not rereceive resend items)
                    if incomingfile.fromchannel:
                        incomingfile.retransmit = not incomingfile.retransmit
                        incomingfile.save()
            else:                                    #coming from ViewIncoming
                viewlib.handlepagination(request.POST,formin.cleaned_data)
        cleaned_data = formin.cleaned_data

    query = models.filereport.objects.all()
    pquery = viewlib.filterquery(query,cleaned_data,incoming=True)
    formout = forms.ViewIncoming(initial=cleaned_data)
    return viewlib.render(request,formout,pquery)

def outgoing(request,*kw,**kwargs):
    if request.method == 'GET':
        if 'select' in request.GET:             #via menu, go to select form
            formout = forms.SelectOutgoing()
            return viewlib.render(request,formout)
        else:                                   #via menu, parse recevied parameters
            cleaned_data = {'page':1,'sortedby':'idta','sortedasc':False,'lastrun':bool(int(request.GET.get('lastrun',0)))}
    else:                                  # request.method == 'POST'
        if '2incoming' in request.POST:        #coming from ViewIncoming, go to outgoing form using same criteria
            request.POST = viewlib.changepostparameters(request.POST,soort='out2in')
            return incoming(request)
        elif '2process' in request.POST:        #coming from ViewIncoming, go to outgoing form using same criteria
            request.POST = viewlib.changepostparameters(request.POST,soort='2process')
            return process(request)
        elif '2confirm' in request.POST:        #coming from ViewIncoming, go to outgoing form using same criteria
            request.POST = viewlib.changepostparameters(request.POST,soort='out2confirm')
            return process(request)
        elif 'fromselect' in request.POST:        #coming from select criteria screen
            formin = forms.SelectOutgoing(request.POST)
            if not formin.is_valid():
                return viewlib.render(request,formin)
        else:
            formin = forms.ViewOutgoing(request.POST)
            if not formin.is_valid():
                return viewlib.render(request,formin)
            elif '2select' in request.POST:         #coming from ViewIncoming, change the selection criteria, go to select form
                formout = forms.SelectOutgoing(formin.cleaned_data)
                return viewlib.render(request,formout)
            elif 'retransmit' in request.POST:        #coming from ViewIncoming
                ta_object = models.ta.objects.get(idta=int(request.POST[u'retransmit']))
                if ta_object.statust != RESEND:     #can only resend last file
                    ta_object.retransmit = not ta_object.retransmit
                    ta_object.save()
            elif 'resendall' in request.POST:
                #select all objects with parameters and set retransmit
                query = models.ta.objects.filter(status=EXTERNOUT)
                outgoingfiles = viewlib.filterquery2(query,formin.cleaned_data)
                for outgoingfile in outgoingfiles:       #can only resend last file
                    if outgoingfile.statust != RESEND:
                        outgoingfile.retransmit = not outgoingfile.retransmit
                        outgoingfile.save()
            elif 'noautomaticretry' in request.POST:        #coming from ViewIncoming
                ta_object = models.ta.objects.get(idta=int(request.POST[u'noautomaticretry']))
                if ta_object.statust == ERROR:
                    ta_object.statust = NO_RETRY
                    ta_object.save()
            else:                                    #coming from ViewIncoming
                viewlib.handlepagination(request.POST,formin.cleaned_data)
        cleaned_data = formin.cleaned_data

    query = models.ta.objects.filter(status=EXTERNOUT)
    pquery = viewlib.filterquery(query,cleaned_data)
    formout = forms.ViewOutgoing(initial=cleaned_data)
    return viewlib.render(request,formout,pquery)

def document(request,*kw,**kwargs):
    if request.method == 'GET':
        if 'select' in request.GET:             #via menu, go to select form
            formout = forms.SelectDocument()
            return viewlib.render(request,formout)
        else:                                   #via menu, parse recevied parameters
            cleaned_data = {'page':1,'sortedby':'idta','sortedasc':False}
            cleaned_data['lastrun'] = bool(int(request.GET.get('lastrun',0)))
            cleaned_data['status'] = int(request.GET.get('status',0))
    else:                                  # request.method == 'POST'
        if 'fromselect' in request.POST:        #coming from select criteria screen
            formin = forms.SelectDocument(request.POST)
            if not formin.is_valid():
                return viewlib.render(request,formin)
        else:
            formin = forms.ViewDocument(request.POST)
            if not formin.is_valid():
                return viewlib.render(request,formin)
            if '2select' in request.POST:         #coming from ViewIncoming, change the selection criteria, go to select form
                formout = forms.SelectDocument(formin.cleaned_data)
                return viewlib.render(request,formout)
            elif 'retransmit' in request.POST:        #coming from Documents, no reportidta
                idta = request.POST[u'retransmit']
                filereport = models.filereport.objects.get(idta=int(idta),statust=DONE)
                filereport.retransmit = not filereport.retransmit
                filereport.save()
            else:                                    #coming from ViewIncoming
                viewlib.handlepagination(request.POST,formin.cleaned_data)
        cleaned_data = formin.cleaned_data

    query = models.ta.objects.filter(django.db.models.Q(status=SPLITUP)|django.db.models.Q(status=TRANSLATED))
    pquery = viewlib.filterquery(query,cleaned_data)
    viewlib.trace_document(pquery)
    formout = forms.ViewDocument(initial=cleaned_data)
    return viewlib.render(request,formout,pquery)

def process(request,*kw,**kwargs):
    if request.method == 'GET':
        if 'select' in request.GET:             #via menu, go to select form
            formout = forms.SelectProcess()
            return viewlib.render(request,formout)
        else:                                   #via menu, parse recevied parameters
            cleaned_data = {'page':1,'sortedby':'idta','sortedasc':False,'lastrun':bool(int(request.GET.get('lastrun',0)))}
    else:                                  # request.method == 'POST'
        if '2incoming' in request.POST:        #coming from ViewIncoming, go to outgoing form using same criteria
            request.POST = viewlib.changepostparameters(request.POST,soort='fromprocess')
            return incoming(request)
        elif '2outgoing' in request.POST:        #coming from ViewIncoming, go to outgoing form using same criteria
            request.POST = viewlib.changepostparameters(request.POST,soort='fromprocess')
            return outgoing(request)
        elif 'fromselect' in request.POST:        #coming from select criteria screen
            formin = forms.SelectProcess(request.POST)
            if not formin.is_valid():
                return viewlib.render(request,formin)
        else:
            formin = forms.ViewProcess(request.POST)
            if not formin.is_valid():
                return viewlib.render(request,formin)
            elif '2select' in request.POST:         #coming from ViewIncoming, change the selection criteria, go to select form
                formout = forms.SelectProcess(formin.cleaned_data)
                return viewlib.render(request,formout)
            else:                                    #coming from ViewIncoming
                viewlib.handlepagination(request.POST,formin.cleaned_data)
        cleaned_data = formin.cleaned_data

    query = models.ta.objects.filter(status=PROCESS,statust=ERROR)
    pquery = viewlib.filterquery(query,cleaned_data)
    formout = forms.ViewProcess(initial=cleaned_data)
    return viewlib.render(request,formout,pquery)

def detail(request,*kw,**kwargs):
    ''' in: the idta, either as parameter in or out.
        in: is idta of incoming file.
        out: idta of outgoing file, need to trace back for incoming file.
        return list of ta's for display in detail template.
        This list is formatted and ordered for display.
        first, get a tree (trace) starting with the incoming ta ;
        than make up the details for the trace
    '''
    if request.method == 'GET':
        if 'inidta' in request.GET: #detail for incoming screen
            rootta = models.ta.objects.get(idta=int(request.GET['inidta']))
        else:                       #detail for outgoing: trace back to EXTERNIN first
            rootta = viewlib.django_trace_origin(int(request.GET['outidta']),{'status':EXTERNIN})[0]
        viewlib.gettrace(rootta)
        detaillist = viewlib.trace2detail(rootta)
        return django.shortcuts.render_to_response('bots/detail.html', {'detaillist':detaillist,'rootta':rootta,},context_instance=django.template.RequestContext(request))

def confirm(request,*kw,**kwargs):
    if request.method == 'GET':
        if 'select' in request.GET:             #via menu, go to select form
            formout = forms.SelectConfirm()
            return viewlib.render(request,formout)
        else:                              #via menu, go to view form for last run
            cleaned_data = {'page':1,'sortedby':'idta','sortedasc':False}
    else:                                  # request.method == 'POST'
        if '2incoming' in request.POST:        #coming from ViewIncoming, go to outgoing form using same criteria
            request.POST = viewlib.changepostparameters(request.POST,soort='confirm2in')
            return incoming(request)
        elif '2outgoing' in request.POST:        #coming from ViewIncoming, go to outgoing form using same criteria
            request.POST = viewlib.changepostparameters(request.POST,soort='confirm2out')
            return outgoing(request)
        elif 'fromselect' in request.POST:        #coming from select criteria screen
            formin = forms.SelectConfirm(request.POST)
            if not formin.is_valid():
                return viewlib.render(request,formin)
        elif 'confirm' in request.POST:        #coming from 'star' menu 'Manual confirm'
            ta_object = models.ta.objects.get(idta=int(request.POST[u'confirm']))
            if ta_object.confirmed == False and ta_object.confirmtype.startswith('ask'):
                ta_object.confirmed = True
                ta_object.confirmidta = '-1'   # to indicate a manual confirmation
                ta_object.save()
                messages.add_message(request, messages.INFO, _(u'Manual confirmed.'))
            else:
                messages.add_message(request, messages.INFO, _(u'Manual confirm not possible.'))
            # then just refresh the current view
            formin = forms.ViewConfirm(request.POST)
            if not formin.is_valid():
                return viewlib.render(request,formin)
        else:
            formin = forms.ViewConfirm(request.POST)
            if not formin.is_valid():
                return viewlib.render(request,formin)
            elif '2select' in request.POST:         #coming from ViewIncoming, change the selection criteria, go to select form
                formout = forms.SelectConfirm(formin.cleaned_data)
                return viewlib.render(request,formout)
            else:                                    #coming from ViewIncoming
                viewlib.handlepagination(request.POST,formin.cleaned_data)
        cleaned_data = formin.cleaned_data

    query = models.ta.objects.filter(confirmasked=True)
    pquery = viewlib.filterquery(query,cleaned_data)
    formout = forms.ViewConfirm(initial=cleaned_data)
    return viewlib.render(request,formout,pquery)

def filer(request,*kw,**kwargs):
    ''' handles bots file viewer. Only files in data dir of Bots are displayed.'''
    if request.method == 'GET':
        try:
            idta = request.GET['idta']
            if idta == 0: #for the 'starred' file names (eg multiple output)
                raise Exception('to be caught')
                
            currentta = list(models.ta.objects.filter(idta=idta))[0]
            if request.GET['action'] == 'downl':
                response = django.http.HttpResponse(mimetype=currentta.contenttype)
                if currentta.contenttype == 'text/html':
                    dispositiontype = 'inline'
                else:
                    dispositiontype = 'attachment'
                response['Content-Disposition'] = dispositiontype + '; filename=' + currentta.filename + '.txt'
                #~ response['Content-Length'] = os.path.getsize(absfilename)
                response.write(botslib.readdata(currentta.filename))
                return response
            elif request.GET['action'] == 'previous':
                if currentta.parent:    #has a explicit parent
                    talijst = list(models.ta.objects.filter(idta=currentta.parent))
                else:                   #get list of ta's referring to this idta as child
                    talijst = list(models.ta.objects.filter(child=currentta.idta))
            elif request.GET['action'] == 'this':
                if currentta.status == EXTERNIN:        #EXTERNIN can not be displayed, so go to first FILEIN
                    talijst = list(models.ta.objects.filter(parent=currentta.idta))
                elif currentta.status == EXTERNOUT:     #EXTERNOUT can not be displayed, so go to last FILEOUT
                    talijst = list(models.ta.objects.filter(idta=currentta.parent))
                else:
                    talijst = [currentta]
            elif request.GET['action'] == 'next':
                if currentta.child:     #has a explicit child
                    talijst = list(models.ta.objects.filter(idta=currentta.child))
                else: 
                    talijst = list(models.ta.objects.filter(parent=currentta.idta))
            for ta_object in talijst:
                #determine if can display file
                if ta_object.filename and ta_object.filename.isdigit():
                    if ta_object.charset:  
                        ta_object.content = botslib.readdata(ta_object.filename,charset=ta_object.charset,errors='ignore')
                    else:   #guess safe choice for charset. alt1: get charset by looking forward (until translation). alt2:try with utf-8, if error iso-8859-1   
                        ta_object.content = botslib.readdata(ta_object.filename,charset='us-ascii',errors='ignore')
                    ta_object.has_file = True
                    if ta_object.editype == 'x12':
                        ta_object.content = viewlib.indent_x12(ta_object.content)
                    elif ta_object.editype == 'edifact':
                        ta_object.content = viewlib.indent_edifact(ta_object.content)
                else:
                    ta_object.has_file = False
                    ta_object.content = _(u'No file available for display.')
                #determine has previous:
                if ta_object.parent or ta_object.status == MERGED:
                    ta_object.has_previous = True
                else:
                    ta_object.has_previous = False
                #determine: has next:
                if ta_object.status == EXTERNOUT or ta_object.statust in [OPEN,ERROR]:
                    ta_object.has_next = False
                else:
                    ta_object.has_next = True
            return  django.shortcuts.render_to_response('bots/filer.html', {'idtas': talijst},context_instance=django.template.RequestContext(request))
        except:
            return  django.shortcuts.render_to_response('bots/filer.html', {'error_content': _(u'No such file.')},context_instance=django.template.RequestContext(request))

def srcfiler(request,*kw,**kwargs):
    ''' handles bots source file viewer. display grammar, mapping, userscript etc.'''
    if request.method == 'GET':
        try:
            src = request.GET['src']
            if botsglobal.ini.get('directories','usersys') in src and src.endswith('.py'): # only python source in usersys!
                with open(src) as f:
                    source = f.read()
                classified_text = py2html.analyze_python(source)
                html_source = py2html.html_highlight(classified_text)
                return  django.shortcuts.render_to_response('bots/srcfiler.html', {'src':src, 'html_source':html_source},context_instance=django.template.RequestContext(request))
            else:
                return  django.shortcuts.render_to_response('bots/srcfiler.html', {'error_content': _(u'File %s not allowed.' %src)},context_instance=django.template.RequestContext(request))
        except:
            #~ print botslib.txtexc()
            return  django.shortcuts.render_to_response('bots/srcfiler.html', {'error_content': _(u'No such file.')},context_instance=django.template.RequestContext(request))

def plugin(request,*kw,**kwargs):
    if request.method == 'GET':
        form = forms.UploadFileForm()
        return django.shortcuts.render_to_response('bots/plugin.html', {'form':form},context_instance=django.template.RequestContext(request))
    else:
        if 'submit' in request.POST:        #coming from ViewIncoming, go to outgoing form using same criteria
            form = forms.UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                #always write backup plugin first
                plugout_backup_core(request,*kw,**kwargs)        
                #read the plugin
                try:
                    if pluglib.read_plugin(request.FILES['file'].temporary_file_path()):
                        messages.add_message(request, messages.INFO, _(u'Overwritten existing files.'))
                except Exception,msg:
                    notification = u'Error reading plugin: "%s".' % str(msg)
                    botsglobal.logger.error(notification)
                    messages.add_message(request, messages.INFO, notification)
                else:
                    notification = _(u'Plugin "%s" is read successful.')%request.FILES['file'].name
                    botsglobal.logger.info(notification)
                    messages.add_message(request, messages.INFO, notification)
                finally:
                    request.FILES['file'].close()   #seems to be needed according to django docs.
            else:
                messages.add_message(request, messages.INFO, _(u'No plugin read.'))
        return django.shortcuts.redirect('/home')

def plugin_index(request,*kw,**kwargs):
    if request.method == 'GET':
        return django.shortcuts.render_to_response('bots/plugin_index.html', context_instance=django.template.RequestContext(request))
    else:
        if 'submit' in request.POST:        #coming from ViewIncoming, go to outgoing form using same criteria
            #always write backup plugin first
            plugout_backup_core(request,*kw,**kwargs)        
            #read the plugin
            try:
                pluglib.read_index('index')
            except Exception,msg:
                notification = u'Error reading configuration index file: "%s".' % str(msg)
                botsglobal.logger.error(notification)
                messages.add_message(request, messages.INFO, notification)
            else:
                notification = _(u'Configuration index file is read successful.')
                botsglobal.logger.info(notification)
                messages.add_message(request, messages.INFO, notification)
        return django.shortcuts.redirect('/home')

def plugout_index(request,*kw,**kwargs):
    if request.method == 'GET':
        filename = botslib.join(botsglobal.ini.get('directories','usersysabs'),'index.py')
        botsglobal.logger.info(_(u'Start writing configuration index file "%s".'),filename)
        try:
            dummy_for_cleaned_data = {'databaseconfiguration':True,'umlists':True,'databasetransactions':False}
            pluglib.make_index(dummy_for_cleaned_data,filename)
        except Exception,msg:
            notification = _(u'Error writing configuration index file: "%s".')%str(msg)
            botsglobal.logger.error(notification)
            messages.add_message(request, messages.INFO, notification)
        else:
            notification = _(u'Configuration index file "%s" is written successful.')%filename
            botsglobal.logger.info(notification)
            messages.add_message(request, messages.INFO, notification)
        return django.shortcuts.redirect('/home')
        
def plugout_backup(request,*kw,**kwargs):
    if request.method == 'GET':
        plugout_backup_core(request,*kw,**kwargs)        
    return django.shortcuts.redirect('/home')
        
def plugout_backup_core(request,*kw,**kwargs):
    filename = botslib.join(botsglobal.ini.get('directories','botssys'),'backup_plugin_%s.zip'%time.strftime('%Y%m%d%H%M%S'))
    botsglobal.logger.info(_(u'Start writing backup plugin "%s".'),filename)
    try:
        dummy_for_cleaned_data = {'databaseconfiguration':True,
                                    'umlists':True,
                                    'fileconfiguration':True,
                                    'infiles':False,
                                    'charset':True,
                                    'databasetransactions':False,
                                    'data':False,
                                    'logfiles':False,
                                    'config':False,
                                    'database':False,
                                    }
        pluglib.make_plugin(dummy_for_cleaned_data,filename)
    except Exception,msg:
        notification = u'Error writing backup plugin: "%s".' % str(msg)
        botsglobal.logger.error(notification)
        messages.add_message(request, messages.INFO, notification)
    else:
        notification = _(u'Backup plugin "%s" is written successful.')%filename
        botsglobal.logger.info(notification)
        messages.add_message(request, messages.INFO, notification)
        
def plugout(request,*kw,**kwargs):
    if request.method == 'GET':
        form = forms.PlugoutForm()
        return  django.shortcuts.render_to_response('bots/plugout.html', {'form': form},context_instance=django.template.RequestContext(request))
    else:
        if 'submit' in request.POST:
            form = forms.PlugoutForm(request.POST)
            if form.is_valid():
                filename = botslib.join(botsglobal.ini.get('directories','botssys'),'plugin_temp.zip')
                botsglobal.logger.info(_(u'Start writing plugin "%s".'),filename)
                try:
                    pluglib.make_plugin(form.cleaned_data,filename)
                except botslib.PluginError, msg:
                    botsglobal.logger.error(str(msg))
                    messages.add_message(request,messages.INFO,str(msg))
                else:
                    botsglobal.logger.info(_(u'Plugin "%s" created successful.'),filename)
                    response = django.http.HttpResponse(open(filename, 'rb').read(), content_type='application/zip')
                    # response['Content-Length'] = os.path.getsize(filename)
                    response['Content-Disposition'] = 'attachment; filename=' + 'plugin' + time.strftime('_%Y%m%d') + '.zip'
                    return response
    return django.shortcuts.redirect('/home')

def delete(request,*kw,**kwargs):
    if request.method == 'GET':
        form = forms.DeleteForm()
        return  django.shortcuts.render_to_response('bots/delete.html', {'form': form},context_instance=django.template.RequestContext(request))
    else:
        if 'submit' in request.POST:
            form = forms.DeleteForm(request.POST)
            if form.is_valid():
                botsglobal.logger.info(_(u'Start deleting in configuration.'))
                if form.cleaned_data['deltransactions']:
                    from django.db import connection, transaction
                    #while testing with very big loads, deleting transaction when wrong. Using raw SQL solved this.
                    cursor = connection.cursor()
                    cursor.execute("DELETE FROM ta")
                    cursor.execute("DELETE FROM filereport")
                    cursor.execute("DELETE FROM report")
                    transaction.commit_unless_managed()
                    messages.add_message(request, messages.INFO, _(u'Transactions are deleted.'))
                    botsglobal.logger.info(_(u'Transactions are deleted.'))
                    #clean data files
                    deletefrompath = botsglobal.ini.get('directories','data','botssys/data')
                    shutil.rmtree(deletefrompath,ignore_errors=True)
                    botslib.dirshouldbethere(deletefrompath)
                    notification = _(u'Data files are deleted.')
                    messages.add_message(request, messages.INFO, notification)
                    botsglobal.logger.info(notification)
                elif form.cleaned_data['delacceptance']:
                    from django.db.models import Min
                    list_file = []  #list of files for deletion in data-directory
                    report_idta_lowest = 0
                    for acc_report in models.report.objects.filter(acceptance=1): #for each acceptance report. is not very efficient.
                        if not report_idta_lowest:
                            report_idta_lowest = acc_report.idta
                        max_report_idta = models.report.objects.filter(idta__gt=acc_report.idta).aggregate(Min('idta'))['idta__min'] #select 'next' report...
                        if not max_report_idta: #if report is report of last run, there is no next report
                            max_report_idta = sys.maxint
                        #we have a idta-range now: from (and including) acc_report.idta till (and excluding) max_report_idta
                        list_file += models.ta.objects.filter(idta__gte=acc_report.idta,idta__lt=max_report_idta).exclude(status=1).values_list('filename', flat=True).distinct()
                        models.ta.objects.filter(idta__gte=acc_report.idta,idta__lt=max_report_idta).delete()   #delete ta in range 
                        models.filereport.objects.filter(idta__gte=acc_report.idta,idta__lt=max_report_idta).delete()   #delete filereports in range
                    if report_idta_lowest:
                        models.report.objects.filter(idta__gte=report_idta_lowest,acceptance=1).delete()     #delete all acceptance reports
                        for filename in list_file:      #delete all files in data directory geenrated during acceptance testing
                            if filename.isdigit():
                                botslib.deldata(filename)
                    notification = _(u'Transactions from acceptance-testing deleted.')
                    messages.add_message(request, messages.INFO, notification)
                    botsglobal.logger.info(notification)
                if form.cleaned_data['delconfiguration']:
                    models.confirmrule.objects.all().delete()
                    models.routes.objects.all().delete()
                    models.channel.objects.all().delete()
                    models.chanpar.objects.all().delete()
                    models.translate.objects.all().delete()
                    models.partner.objects.all().delete()
                    notification = _(u'Database configuration is deleted.')
                    messages.add_message(request, messages.INFO, notification)
                    botsglobal.logger.info(notification)
                if form.cleaned_data['delcodelists']:
                    models.ccode.objects.all().delete()
                    models.ccodetrigger.objects.all().delete()
                    notification = _(u'User code lists are deleted.')
                    messages.add_message(request, messages.INFO, notification)
                    botsglobal.logger.info(notification)
                if form.cleaned_data['delinfile']:
                    deletefrompath = botslib.join(botsglobal.ini.get('directories','botssys','botssys'),'infile')
                    shutil.rmtree(deletefrompath,ignore_errors=True)
                    notification = _(u'Files in botssys/infile are deleted.')
                    messages.add_message(request, messages.INFO, notification)
                    botsglobal.logger.info(notification)
                if form.cleaned_data['deloutfile']:
                    deletefrompath = botslib.join(botsglobal.ini.get('directories','botssys','botssys'),'outfile')
                    shutil.rmtree(deletefrompath,ignore_errors=True)
                    notification = _(u'Files in botssys/outfile are deleted.')
                    messages.add_message(request, messages.INFO, notification)
                    botsglobal.logger.info(notification)
                if form.cleaned_data['deluserscripts']:
                    deletefrompath = botsglobal.ini.get('directories','usersysabs')
                    for root, dirs, files in os.walk(deletefrompath):
                        head, tail = os.path.split(root)
                        if tail == 'charsets':
                            del dirs[:]
                            continue
                        for bestand in files:
                            if bestand != '__init__.py':
                                os.remove(os.path.join(root,bestand))
                    notification = _(u'User scripts are deleted (in usersys).')
                    messages.add_message(request, messages.INFO, notification)
                    botsglobal.logger.info(notification)
                elif form.cleaned_data['delbackup']:
                    deletefrompath = botsglobal.ini.get('directories','usersysabs')
                    for root, dirs, files in os.walk(deletefrompath):
                        head, tail = os.path.split(root)
                        if tail == 'charsets':
                            del dirs[:]
                            continue
                        for bestand in files:
                            name,ext = os.path.splitext(bestand)
                            if ext and len(ext) == 15 and ext[1:].isdigit() :
                                os.remove(os.path.join(root,bestand))
                    notification = _(u'Backupped user scripts are deleted/purged (in usersys).')
                    messages.add_message(request, messages.INFO, notification)
                    botsglobal.logger.info(notification)
                botsglobal.logger.info(_(u'Finished deleting in configuration.'))
    return django.shortcuts.redirect('/home')


def runengine(request,*kw,**kwargs):
    if request.method == 'GET':
        #needed to find out right arguments:
        # 1. python_executable_path. Problem in virtualenv. Use setting in bots.ini if there
        # 2. botsengine_path. Problem in apache. Use setting in bots.ini if there
        # 3. environment (config). OK
        # 4. commandstorun (eg --new) and routes. OK
        python_executable_path = botsglobal.ini.get('settings','python_executable_path',sys.executable)
        botsengine_path = botsglobal.ini.get('settings','botsengine_path',os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),'bots-engine.py'))
        environment = '-c' + botsglobal.ini.get('directories','config_org')
        lijst = [python_executable_path,botsengine_path,environment]
        # get 4. commandstorun (eg --new) and routes via request
        if 'clparameter' in request.GET:
            lijst.append(request.GET['clparameter'])
            
        #either bots-engine is run directly or via jobqueue-server:
        if botsglobal.ini.getboolean('jobqueue','enabled',False):   #run bots-engine via jobqueue-server; reports back if job is queued
            import job2queue
            terug = job2queue.send_job_to_jobqueue(lijst)
            messages.add_message(request, messages.INFO, job2queue.JOBQUEUEMESSAGE2TXT[terug])
            botsglobal.logger.info(job2queue.JOBQUEUEMESSAGE2TXT[terug])
        else:                                                       #run bots-engine direct.; reports back if bots-engien is started succesful. **not reported: problems with running.
            botsglobal.logger.info(_(u'Run bots-engine with parameters: "%s"'),str(lijst))
            #first check if another instance of bots-engine is running/if port is free
            try:
                engine_socket = botslib.check_if_other_engine_is_running()
            except socket.error:
                notification = _(u'Trying to run "bots-engine", but another instance of "bots-engine" is running. Please try again later.')
                messages.add_message(request, messages.INFO, notification)
                botsglobal.logger.info(notification)
                return django.shortcuts.redirect('/home')
            else:
                engine_socket.close()   #and close the socket
            #run engine
            try:
                terug = subprocess.Popen(lijst).pid
            except Exception,msg:
                notification = _(u'Errors while trying to run bots-engine: "%s".')%msg
                messages.add_message(request, messages.INFO, notification)
                botsglobal.logger.info(notification)
            else:
                messages.add_message(request, messages.INFO, _(u'Bots-engine is started.'))
    return django.shortcuts.redirect('/home')

def sendtestmailmanagers(request,*kw,**kwargs):
    try:
        sendornot = botsglobal.ini.getboolean('settings','sendreportiferror',False)
    except botslib.BotsError:
        sendornot = False
    if not sendornot:
        notification = _(u'Trying to send test mail, but in bots.ini, section [settings], "sendreportiferror" is not "True".')
        botsglobal.logger.info(notification)
        messages.add_message(request, messages.INFO, notification)
        return django.shortcuts.redirect('/home')

    from django.core.mail import mail_managers
    try:
        mail_managers(_(u'testsubject'), _(u'test content of report'))
    except:
        txt = botslib.txtexc()
        messages.add_message(request, messages.INFO, _(u'Sending test mail failed.'))
        botsglobal.logger.info(_(u'Sending test mail failed, error:\n%s(txt)'), {'txt':txt})
        return django.shortcuts.redirect('/home')
    notification = _(u'Sending test mail succeeded.')
    messages.add_message(request, messages.INFO, notification)
    botsglobal.logger.info(notification)
    return django.shortcuts.redirect('/home')


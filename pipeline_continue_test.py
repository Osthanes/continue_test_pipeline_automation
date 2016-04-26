#!/usr/bin/python

#***************************************************************************
# Copyright 2015 IBM
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#***************************************************************************

import argparse
import json
import os
import requests
import sys
import traceback
import time
import ConfigParser
import string
import urlparse

# Environment variables
IDS_USER_ENV_VAR = 'ibmIdUsername'
IDS_PASS_ENV_VAR = 'ibmIdPassword'
LOGIN_URL = ""
jazzHubHost = ""

def main():
    global LOGIN_URL
    # Read the IDS Project info from pipeline_test.properties
    config = ConfigParser.ConfigParser() 
    config.read('pipeline_test.properties')
    jazzHubHost = config.get('Config', 'jazzHubHost')
    jazzHubProjectName = config.get('Config', 'jazzHubProjectName')
    jazzHubProjectName = string.replace(jazzHubProjectName, ' | ', '/')
    idsProjectURL = '%s/pipeline/%s' % (jazzHubHost, jazzHubProjectName)
    print "\nIDS project URL: %s" % (idsProjectURL) 
    if jazzHubHost == "https://beta3.hub.jazz.net":
        LOGIN_URL = "https://psdev.login.jazz.net"
    elif jazzHubHost == "https://qa.hub.jazz.net":
        LOGIN_URL = "https://stg.login.jazz.net"
    elif jazzHubHost == "https://hub.jazz.net":
        LOGIN_URL = "https://login.jazz.net"
    else:
        LOGIN_URL = "https://psdev.login.jazz.net"

    print ('Target login URL is: %s' % LOGIN_URL)

    # Number of retries to attempt
    RETRY = 5
    # Get the login cookies
    # Get the login cookies, try both login methods
    cookies = None
    # Get the login cookies, try both login methods
    cookies = None
    for i in range(RETRY):
        for f in [ssologin, ssologin_old]:
            try:
                cookies = f()
                break
            except Exception, e:
                if i < RETRY - 1:
                    print '\nFailed to log into IDS'
                    traceback.print_exc(file=sys.stdout)
                    time.sleep(10)
                else:
                    raise e
        if cookies:
            break
    print 'Successfully logged into IDS, getting pipeline information ...'

    # headers
    headers = {
        'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
    }

    # Get current stages information
    sleepTime = 20;
    curr_pipe_info = []
    print "\nStages execution status before trigger stage:"
    curr_pipe_info = getStageStatus(idsProjectURL, cookies, headers, sleepTime)
    if curr_pipe_info:
        print "\nSuccessfully retrieved pipeline information before trigger stage ..."
        for item in curr_pipe_info:
            print item[0], ', '.join(map(str, item[1:]))
    else:
        raise Exception("\nThe project '%s' does not have pipeline stage." % jazzHubProjectName)


    # Trigger the first stage
    stage_id = curr_pipe_info[0][0]
    print "\nTriggering the stage '%s' with Id  %s ..." % (curr_pipe_info[0][1], stage_id)
    url = '%s/stages/%s/executions' % (idsProjectURL, stage_id)
    r = requests.post(url, headers=headers, cookies=cookies)
    if r.status_code != 201:
        raise Exception('Failed to POST %s, status code %s\n%s' %
                        (url, r.status_code, r.content))
    print "Successfully triggered stage '%s'" % (curr_pipe_info[0][1])

    # Get next stages information
    ret = 0
    retries = 0
    sleepTime = 45;
    while retries < 15:
        next_pipe_info = []
        print "\nStages execution status after triggered stage:"
        next_pipe_info = getStageStatus(idsProjectURL, cookies, headers, sleepTime)
        if next_pipe_info:
            print "\nSuccessfully retrieved pipeline information after triggered stage ..."
            for item in next_pipe_info:
                print item[0], ', '.join(map(str, item[1:]))
        else:
            raise Exception("\nThe project '%s' does not have pipeline stage." % jazzHubProjectName)

        ret = checkStageStatus(idsProjectURL, curr_pipe_info, next_pipe_info)
        print "\nret: %s" %(ret)
        if ret != 2:
            break
        time.sleep(sleepTime)
        retries = retries + 1

    exit(ret)


def getStageStatus(url, cookies, headers, sleepTime):

    url = '%s/latest-executions' % url

    while True:
        # Get the pipeline information
        print "URL: ", url
#        print "headers: ", headers
#        print "cookies: ", cookies
        r = requests.get(url, headers=headers, cookies=cookies)
        if r.status_code != 200:
            raise Exception('Failed to GET %s, status code %s' %
                            (url, r.status_code))
    
#        print "r.content:"
#        print (r.content)
        data = json.loads(r.content)

        if not 'stages' in data:
            raise Exception("output does not contain 'stages'")
        stages = data['stages']

        if not stages:
            print "WARNING: Pipeline does not have any stages."
            break

        stage_ids = []
        stage_names = []
        jobIds = []
        jobCompNames = []    
        for stage in stages:
            jobs = stage.get('jobs')
            for job in jobs:
                jobIds.append(job.get('id'))
                jobCompNames.append(job.get('componentName'))
                stage_ids.append(stage.get('id'))
                stage_names.append(stage.get('name'))        
        
        if not 'executions' in data:
            raise Exception("output does not contain 'executions'")
        executions = data['executions']

        if not executions:
            print "WARNING: Pipeline does not have any job executions."
            break

        jobExecutionStatuses = []
        jobExecutionNumbers = []
        jobExecutionTypes = []
        jobExecutionJobIds = []
        exeStatuses = []
        jobinfo = []
        for execution in executions:
            jobExecutions = execution.get('jobExecutions')
            for jobExecution in jobExecutions:
                jobExecutionJobIds.append(jobExecution.get('jobId'))
                exeStatuses.append(execution.get('status'))
                jobExecutionStatuses.append(jobExecution.get('jobExecution',{}).get('status'))
                jobExecutionNumbers.append(jobExecution.get('jobExecution',{}).get('number'))
                jobExecutionTypes.append(jobExecution.get('jobExecution',{}).get('type'))

        findJobExecution = False
        for jobId in jobIds:
            mustContinue = False
            jIndex = jobIds.index(jobId)
            theStageId = stage_ids[jIndex]
            theStageName = stage_names[jIndex]
            theCompName = jobCompNames[jIndex]
            sb = []
            for jobExecutionJobId in jobExecutionJobIds:
                if jobId == jobExecutionJobId:
                    findJobExecution = True
                    jeIndex = jobExecutionJobIds.index(jobExecutionJobId)
                    theStageExeStatus = exeStatuses[jeIndex]
                    theJobStatus = jobExecutionStatuses[jeIndex]
                    theJobNumber = jobExecutionNumbers[jeIndex]
                    theJobType = jobExecutionTypes[jeIndex]
                    theJobId = jobId;

                    print "stage status: '%s', job_name: '%s', job_type: '%s', job_number: '%s', job_status: '%s'" % (theStageExeStatus, theCompName, theJobType, theJobNumber, theJobStatus)

                    if theStageExeStatus == "RUNNING" or theStageExeStatus == "QUEUED" or theStageExeStatus == "NEW":
                        mustContinue = True
                    elif theJobStatus == "IN_PROGRESS" or theJobStatus == "QUEUED" or theJobStatus == "None":
                        mustContinue = True
                    else:
                        sb.append(theStageId)
                        sb.append(theStageName)
                        sb.append(theStageExeStatus)
                        sb.append(theJobId)
                        sb.append(theCompName)
                        sb.append(theJobType)
                        sb.append(theJobNumber)
                        sb.append(theJobStatus)
                        jobinfo.append(sb)
                    break
            if findJobExecution:
                 findJobExecution = False
            else:    
                print "WARNING: Pipeline job id: '%s' does not have any results.  Most likely this means this part of the pipeline has not been run" % (jobId)
            if mustContinue:
                break
        if mustContinue:                   
            time.sleep(sleepTime)
        else:
            break
            
    return jobinfo

def checkStageStatus(url, before, after):

    for before_item in before:
        matched = False;
        for after_item in after:
            if before_item[3] == after_item[3]:
                matched = True
                # Make sure the job types are matches for before and after
                if before_item[5] != after_item[5]:
                    print "\nFailure, expected matching stage types but got: %s : %s" % (before_item[5], after_item[5])
                    print "Stage Name: %s" % (after_item[1])
                    print "Job Type: %s" % (after_item[5])
                    print "Job Name: %s" % (after_item[4])
                    print "Job URL: %s/%s/%s" % (url, after_item[0], after_item[3])
                    return 1
                # Make sure the job number has incremented by one
                if (int(before_item[6])+1) != int(after_item[6]):
                    print "\nFailure, expected incremented stages but got: %s %s : %s %s" % (before_item[5], before_item[6], after_item[5], after_item[6])
                    print "Stage Name: %s" % (after_item[1])
                    print "Job Type: %s" % (after_item[5])
                    print "Job Name: %s" % (after_item[4])
                    print "Job URL: %s/%s/%s" % (url, after_item[0], after_item[3])
                    return 2

				# Make sure "after" has value of SUCCESS
                if after_item[7] != "SUCCESS":
                    print "\nFailure, expected SUCCESS but got: %s" % (after_item[7])
                    print "Stage Name: %s" % (after_item[1])
                    print "Job Type: %s" % (after_item[5])
                    print "Job Name: %s" % (after_item[4])
                    print "Job URL: %s/%s/%s" % (url, after_item[0], after_item[3])
                    return 3
                # If we have matched, break out of our loop of afters
                break;
		# Check if we have matched and if not, throw error:
        if not matched:
            i = before.index(before_item)
            print "\nFailure, could not find match after pipeline run for stage: %s" % (before[i])
            print "Stage Name: %s" % (before_item[1])
            print "Job Type: %s" % (before_item[5])
            print "Job Name: %s" % (before_item[4])
            print "Job URL: %s/%s/%s" % (url, before_item[0], before_item[3])
            return 5
    return 0

def ssologin():
    global LOGIN_URL
    '''
    Login into IDS using the user/pass in the environment variables; this does
    uses the BlueID.
    '''
    print ('Attempting to log into IDS as %s ...'
           % os.environ.get(IDS_USER_ENV_VAR))

    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }

    # GET on https://login.jazz.net
    params = {
        'redirect_uri': 'https://hub.jazz.net/'
    }
    url = LOGIN_URL + '/psso/proxy/jazzlogin'
    r = session.get(url, params=params, headers=headers)
    if r.status_code != 200:
        raise Exception('Failed to GET %s, status code %s' %
                        (url, r.status_code))
    redirect_url = r.history[-1].url
    redirect_url_parser = urlparse.urlparse(redirect_url)
    html = r.content

    # Parse out the cookie and the IDASS URL, the following regex should work but
    # it is not so manually parse it out
    #regex = r'.*document.cookie="(.*?)=".*window.location.replace\("(.*?)"\).*'

    key = 'document.cookie="'
    index = html.find(key)
    html = html[index + len(key):]
    cookie_val = html[0: html.find('="')]
    c = requests.cookies.create_cookie(cookie_val, redirect_url,
                                       domain=redirect_url_parser.hostname,
                                       path='/')
    session.cookies.set_cookie(c)

    key = 'window.location.replace("'
    index = html.find(key)
    html = html[index + len(key):]
    idaas_url = html[0: html.find('")')]
    idaas_url_parser = urlparse.urlparse(idaas_url)

    # GET on the IDASS URL to setup the cookies
    r = session.get(idaas_url, headers=headers)
    if r.status_code != 200:
        raise Exception('Failed to GET %s, status code %s' %
                        (url, r.status_code))

    # Login IDASS page, get the form action
    url = ('https://%s/idaas/mtfim/sps/idaas/login?%s' %
        (idaas_url_parser.hostname, idaas_url_parser.query))
    r = session.get(url, headers=headers)
    if r.status_code != 200:
        raise Exception('Failed to GET %s, status code %s' %
                        (url, r.status_code))

    # Parse out the action for the ibmid-signin-form
    for line in r.content.split('\n'):
        if "ibmid-signin-form" not in line:
            continue
        key = 'action="'
        index = line.find(key)
        action = line[index + len(key): line.rfind('"')]
        break
    else:
        raise Exception('Failed to parse ibmid-signin-form')

    # POST to sign-in form
    url = 'https://%s%s' % (idaas_url_parser.hostname, action)
    payload = {
        'operation': 'verify',
        'login-form-type': 'pwd',
        'username': os.environ.get(IDS_USER_ENV_VAR),
        'password': os.environ.get(IDS_PASS_ENV_VAR)
    }
    r = session.post(url, data=payload, headers=headers)
    if r.status_code != 200:
        raise Exception('Failed to POST %s, status code %s\n%s' %
                        (url, r.status_code, r.content))

    # At this point the cookies should be set
    return requests.utils.dict_from_cookiejar(session.cookies)


def ssologin_old():
    global LOGIN_URL
    '''
    Login into IDS using the user/pass in the environment variables; this does
    not use the BlueID.
    '''
    print ('Attempting to log into IDS as %s ...'
           % os.environ.get(IDS_USER_ENV_VAR))

    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }

    # GET on https://login.jazz.net
    params = {
        'redirect_uri': 'https://hub.jazz.net/'
    }
    url = LOGIN_URL + '/psso/proxy/jazzlogin'
    r = session.get(url, params=params, headers=headers)
    if r.status_code != 200:
        raise Exception('Failed to GET %s, status code %s\n%s' %
                        (url, r.status_code, r.content))
    redirect_url = r.history[-1].url
    redirect_url_parser = urlparse.urlparse(redirect_url)
    authority = redirect_url_parser.netloc

    # POST to tamlogin.jsp
    payload = {
        'HTTP_BASE': 'http://%s' % authority,
        'HTTPS_BASE': 'https://%s:443'  % authority,
        'PROTOCOL': redirect_url_parser.scheme,
        'URL': '%s?%s' % (redirect_url_parser.path, redirect_url_parser.params),
        'ERROR': ''
    }
    url = 'https://%s/idaas/public/tamlogin.jsp' % authority
    r = session.post(url, data=payload, headers=headers)
    if r.status_code != 200:
        raise Exception('Failed to POST %s, status code %s\n%s' %
                        (url, r.status_code, r.content))

    # GET on saml
    params = {
        'RequestBinding': 'HTTPPost',
        'ResponseBinding': 'HTTPPost',
        'NameIdFormat': 'Email',
        'PartnerId': 'https://%s/sps/saml20sp/saml20' % authority
    }
    sso_url = 'https://www-947.ibm.com'
    url = '%s/FIM/sps/IBM_WWW_SAML20_EXTERNAL/saml20/logininitial' % sso_url
    r = session.get(url, params=params, headers=headers)
    if r.status_code != 200:
        raise Exception('Failed to GET %s, status code %s' %
                        (url, r.status_code))
    sso_url_parser = urlparse.urlparse(r.url)
    page = '%s?%s' % (sso_url_parser.path, sso_url_parser.query)

    params = {
        'persistPage': 'true',
        'page': page,
        'PD-REFERER': authority,
        'error': ''
    }
    sso_login_url = 'https://www-947.ibm.com/account/userservices/jsp/login.jsp'
    r = session.get(sso_login_url, params=params, headers=headers)
    if r.status_code != 200:
        raise Exception('Failed to GET %s, status code %s' %
                        (url, r.status_code))

    # POST on pkmslogin
    payload = {
        'login-form-type': 'pwd',
        'username': os.environ.get(IDS_USER_ENV_VAR),
        'password': os.environ.get(IDS_PASS_ENV_VAR)
    }
    url = 'https://www-947.ibm.com/pkmslogin.form'
    r = session.post(url, data=payload, headers=headers)
    if r.status_code != 200:
        raise Exception('Failed to POST %s, status code %s\n%s' %
                        (url, r.status_code, r.content))
    body = r.content

    # Cleanup the data, if previous line doesn't end with a '>' then append
    lines = []
    for line in body.split('\n'):
        line = line.strip()
        if len(lines) == 0 and not line.startswith('<form method="post"'):
            continue
        if line.startswith('</form>'):
            break
        if len(lines) == 0:
            lines.append(line)
        elif not lines[-1].endswith('>'):
            lines[-1] = lines[-1] + line
        else:
            lines.append(line)

    # Extract the action URL from the "post" form
    action_url = None
    form_data = {}
    for line in lines:
        line = line.strip()
        if line.startswith('<form method="post"'):
            key = 'action="'
            index = line.index(key)
            if index == -1:
                continue
            line = line[index + len(key):]
            action_url = line[0: line.index('"')]
        elif line.startswith('<input type="hidden"'):
            key = 'name="'
            index = line.index(key)
            if index == -1:
                continue
            line = line[index + len(key):]
            param_name = line[0: line.index('"')]
            key = 'value="'
            index = line.index(key)
            if index == -1:
                continue
            line = line[index + len(key):]
            param_val = line[0: line.index('"')]
            form_data[param_name] = param_val

    if not action_url:
        raise Exception('Failed to retrieve form action URL from %s' % url)
    if not form_data:
        raise Exception('Failed to retrieve form data from %s' % url)

    # POST on action URL (https://idaas.ng.bluemix.net/sps/saml20sp/saml20/login)
    url = action_url
    r = session.post(url, data=form_data, headers=headers)
    if r.status_code != 200:
        raise Exception('Failed to POST %s, status code %s\n%s' %
                        (url, r.status_code, r.content))

    # At this point the cookies should be set
    return requests.utils.dict_from_cookiejar(session.cookies)

if __name__ == "__main__":
    try:
        for var in [IDS_USER_ENV_VAR, IDS_PASS_ENV_VAR]:
            if not os.environ.get(var):
                print "'%s' env var must be set" % var
                exit(-1)
        main()
    except Exception, e:
        traceback.print_exc(file=sys.stdout)
        sys.exit(-1)
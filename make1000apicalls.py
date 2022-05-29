#!/usr/local/bin/python3
### use semaphore. the best performance (60 seconds for 1100+ API calls)
import json
import os
import sys
import string
import time
import requests
import aiohttp
import asyncio
from aiohttp import ClientSession
from requests.exceptions import HTTPError


cwd = os.getcwd() # get current working directory

# Open the input para file
inputFile = cwd + "/" + sys.argv[1]
print(inputFile)
try:
    with open(inputFile) as filehandle:
        paras = json.load(filehandle) 
except:
    print('Import failed - unable to open',inputFile)

proxy_url = paras["proxy_url"]
myrefresh_token = paras["myrefresh_token"]


# define the logfile
date = time.strftime("%Y-%m-%d-%H-%M-%S")

log_file = cwd + "/" + "asyncio_run-"+date +".txt"

### get access token
api_url = "https://console.cloud.vmware.com/csp/gateway/am/api/auth/api-tokens/authorize"
def getAccessToken(refresh_token):
        """ Gets the Access Token using the Refresh Token """
        params = {'refresh_token': refresh_token}
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url=api_url, params=params, headers=headers)
        jsonResponse = response.json()
        try:
            access_token = jsonResponse['access_token']
        except:
            access_token = ""
        return access_token

access_token = getAccessToken(myrefresh_token)

# Authentication header
myHeader = {"Content-Type": "application/json","Accept": "application/json", 'csp-auth-token': access_token }

### create API request body for creating NSX-T service

# load the NSX-T service json file
fname = cwd + "/servicesvmw.json"
try:
    with open(fname) as filehandle:
        services = json.load(filehandle)
        # services is <class 'list'>
except:
    print('Import failed - unable to open',fname)

# create the request body

services_list = []

for service in services:
    json_data = {}
    if service["_create_user"]!= "admin" and service["_create_user"]!="admin;admin" and service["_create_user"]!="system":
        json_data["id"] = service["id"]
        json_data["resource_type"]=service["resource_type"]
        json_data["display_name"]=service["display_name"]
        if "description" in service:
            json_data["description"]=service["description"]
        if "tages" in service:
            json_data["tages"]=service["tages"]
        service_entries = []
        for entry in service["service_entries"]:
            modified_entry = {}
            ###
            if "l4_protocol" in entry:
                modified_entry["l4_protocol"] = entry["l4_protocol"]
                modified_entry["source_ports"] = entry["source_ports"]
                modified_entry["destination_ports"] = entry["destination_ports"]
            elif entry["resource_type"] == "ALGTypeServiceEntry":
                modified_entry["alg"] = entry["alg"]
                modified_entry["source_ports"] = entry["source_ports"]
                modified_entry["destination_ports"] = entry["destination_ports"]
            else:
                if "protocol" in entry: 
                    if entry["protocol"] == "ICMPv4":
                        modified_entry["protocol"] = entry["protocol"]
                        if "icmp_type" in entry:
                            modified_entry["icmp_type"] = entry["icmp_type"]
                            if "icmp_code" in entry:
                                modified_entry["icmp_code"] = entry["icmp_code"]
                    else:
                        print(entry["display_name"])
                        print(entry["protocol"])
                #else:
                #    print("service entry: " + entry["display_name"])
            if "tags" in entry:
                modified_entry["tags"] = entry["tags"]
            ###    
            modified_entry["resource_type"] = entry["resource_type"]
            modified_entry["id"] = entry["id"]
            modified_entry["display_name"] = entry["display_name"]
            service_entries.append (modified_entry)
        json_data["service_entries"]=service_entries
        services_list.append(json_data)                

### Make API called to update the service

f = open(log_file, "a")

async def addservice(session,service, sema):
    nsxm_url = proxy_url + "/policy/api/v1/infra/services/" + service["id"]
    try:
        async with sema:
            response = await session.request(method='Patch', url=nsxm_url, headers=myHeader, json=service, ssl=False)
            #response.raise_for_status()
            f.write(f"Response status ({nsxm_url}): {response.status}\n")
    except HTTPError as http_err:
        f.write(f"HTTP error occurred: {http_err}\n")
    except Exception as err:
        f.write(f"An error ocurred: {err}\n")

async def main():
    sema = asyncio.Semaphore(40)
    tasks = []
    async with aiohttp.ClientSession() as session:    
        for service in services_list:
            tasks.append(addservice(session,service, sema))
        await asyncio.gather(*tasks)
            
if __name__ == "__main__":
    start_time = time.time()
    asyncio.run(main())
    print("--- %s seconds ---" % (time.time() - start_time))
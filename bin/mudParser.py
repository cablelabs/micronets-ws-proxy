#!/usr/bin/python

# MUD JSON file => ACLs.

import json
import socket

class MudParser:

    # def getToDeviceACL(ace):
    # def getFromDeviceACL(ace):
    #def getACL(mudObj, deviceIP):
    #def getACL(deviceIP):
    def getACL(self, version, mudObj, deviceIP):

        #deviceIP = "1.1.1.1"

        #
        # Parse the JSON MUD file to extract Match rules"
        #
        #jsonfile =  open("lightbulb.json", "r") 
        #mudObj = json.load(jsonfile)
        #jsonfile.close()

        # the name of from-device-policy 
        fromDevicePolicyName=mudObj["ietf-mud:mud"]["from-device-policy"]\
                                   ["access-lists"]["access-list"][0]["name"]

        # the name of to-device-policy 
        toDevicePolicyName=mudObj["ietf-mud:mud"]["to-device-policy"]\
                                 ["access-lists"]["access-list"][0]["name"]

     
        #
        # In the case there are multiple access-lists for each direction
        #
        # num = len(outBoundACLs)
        # for item in range(num):
        #     print(outBoundACLs[item]["name"])

        # num = len(inBoundACLs)
        # for item in range(num):
        #    print(inBoundACLs[item]["name"])

        # Actual ACLs
        if fromDevicePolicyName == \
                mudObj["ietf-access-control-list:acls"]["acl"][0]["name"]: 
            fromDeviceACL= \
                mudObj["ietf-access-control-list:acls"]["acl"][0]["aces"]["ace"]
            toDeviceACL= \
                mudObj["ietf-access-control-list:acls"]["acl"][1]["aces"]["ace"]
        else:
            fromDeviceACL= \
                mudObj["ietf-access-control-list:acls"]["acl"][1]["aces"]["ace"]
            toDeviceACL= \
                mudObj["ietf-access-control-list:acls"]["acl"][0]["aces"]["ace"]
        
        # aclData= '{"acls": [{"sip": "10.10.1.1", "dip": "0.0.0.0", "sport": 0, "dport":"80","action": "accept" }]}' 

        flowRules = {}

        if version == "1.0":
            flowRules= {"acls": []}
        elif version == "1.1":
            flowRules = {"device": {"deviceId": "", "macAddress": {"eui48": ""}, "networkAddress": {"ipv4": ""},  "allowHosts": [], "denyHosts": [] } }

            flowRules["device"]["networkAddress"]["ipv4"] = deviceIP
        #
        # Obtain fromDeviceACL
        #
        num = len(fromDeviceACL)
        for i in range(num):
            sip = None
            if "ietf-mud:mud" in fromDeviceACL[i]["matches"] and \
               "local-networks" in fromDeviceACL[i]["matches"]["ietf-mud:mud"]: 
                sip = fromDeviceACL[i]["matches"]["ietf-mud:mud"]["local-networks"][0]
            if sip == None: 
                sip = deviceIP

            dip = None
            if "ipv4" in fromDeviceACL[i]["matches"] and \
                    "ietf-acldns:dst-dnsname" in fromDeviceACL[i]["matches"]["ipv4"]: 
                dip = fromDeviceACL[i]["matches"]["ipv4"]["ietf-acldns:dst-dnsname"]

            if "ietf-mud:mud" in fromDeviceACL[i]["matches"] and \
                    "controller" in fromDeviceACL[i]["matches"]["ietf-mud:mud"]: 
                dip = fromDeviceACL[i]["matches"]["ietf-mud:mud"]["controller"]

            sport = 0
            if "tcp" in fromDeviceACL[i]["matches"] and \
                    "source-port" in fromDeviceACL[i]["matches"]["tcp"]: 
                sport = fromDeviceACL[i]["matches"]["tcp"]["source-port"]["port"]

            dport = 0
            if "tcp" in fromDeviceACL[i]["matches"] and \
                    "destination-port" in fromDeviceACL[i]["matches"]["tcp"]: 
                dport = fromDeviceACL[i]["matches"]["tcp"]["destination-port"]["port"]

            action = fromDeviceACL[i]["actions"]["forwarding"]

            if version == "1.0": 
                flowRules["acls"].append({"sip":sip, "dip":dip, \
                                      "sport": sport, "dport":dport, \
                                      "action": action}) 
            elif version == "1.1": 
                if action == "accept" and dip != None : 
                    flowRules["device"]["allowHosts"].append(dip)
                elif action == "reject": 
                    flowRules["device"]["denyHosts"].append(dip)

        #
        # Obtain toDeviceACL
        #
#        num = len(toDeviceACL)
#        for i in range(num):
#            dip = toDeviceACL[i]["matches"]["ietf-mud:mud"]["local-networks"][0]
#            #if dip == "null": 
#            if dip == None: 
#                dip = deviceIP
#
#            sip = "0.0.0.0"
#            dport = 0
#            sport = toDeviceACL[i]["matches"]["tcp"]["source-port"]["port"]
#            action = toDeviceACL[i]["actions"]["forwarding"]
#
#            if version == "1.0": 
#                flowRules["acls"].append({"sip":sip, "dip":dip, \
#                                      "sport": sport, "dport":dport, \
#                                       "action": action}) 

        #  print(flowRules)

        #host = sip.split("//",1)[1]
        #host = host.split("/", 1)[0]
        #print(host)
        #TranslatedIp = socket.gethostbyname(host)
        #print(TranslatedIp)

        return flowRules
     
if __name__ == '__main__':

    mud = MudParser()

    jsonfile =  open("lightbulb.json", "r") 
    mudObj = json.load(jsonfile)
    jsonfile.close()

    mud.getACL(mudObj, "1.1.1.1")

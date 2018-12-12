import requests


flowRules = {"device": {"deviceId": "", "macAddress": {"eui48": ""}, "networkAddress": {"ipv4": ""},  "allowHosts": [], "denyHosts": [] } }

if "allowHosts" in flowRules["device"]:
    flowRules["device"]["allowHosts"].append("abcdef")
    print flowRules
#
#if "abc" in flowRules:
#    print flowRules
#else:
#    print "abc is not a key"

#exit()

r=requests.request('POST', 'http://45.79.13.134:8888/getFlowRules',\
        json={'url': 'http://45.79.13.134:8888/micronets-mud/lightbulb.json', 'version': '1.0', 'ip': '9.9.9.9'})
print r.status_code
print r.text

r=requests.request('POST', 'http://45.79.13.134:8888/getFlowRules',\
        json={'url': 'https://dev.alpineseniorcare.com/micronets-mud/BQ0LDQsMDAM', 'version': '1.1', 'ip': '9.9.9.1'})
print r.status_code
print r.text

r=requests.request('POST', 'http://45.79.13.134:8888/getFlowRules',\
        json={'url': 'https://dev.alpineseniorcare.com/micronets-mud/CQQPBgMCCwk', 'version': '1.1', 'ip': '9.9.9.2'})
print r.status_code
print r.text

r=requests.request('POST', 'http://45.79.13.134:8888/getFlowRules',\
        json={'url': 'https://dev.alpineseniorcare.com/micronets-mud/DgYHAAALAgQ', 'version': '1.1', 'ip': '9.9.9.3'})
print r.status_code
print r.text



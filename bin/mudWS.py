import cherrypy
import requests
import json
import mudParser


class MudManagerWS(object):

    @cherrypy.expose
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def getFlowRules(self): 

        # Obtain the request body in JSON
        data = cherrypy.request.json

        #
        # download mud file from the mud server
        #
        req = requests.request('GET', data['url'])
        if req.status_code != 200:
            return "Cannot download MUD file: " + data['url']

        version = data['version']

        if version != '1.0' and version != '1.1':
            return "Version " + version + " is not supported!"

        deviceIP = data['ip']
        #
        # Parse MUD file to obtain ACLs
        #
        mudObj = json.loads(req.text)

        mud = mudParser.MudParser()
        flowRules = mud.getACL(version, mudObj, deviceIP)

        #aclData= '{"acls": [{"sip": "10.10.1.1", "dip": "0.0.0.0", "sport": 0, "dport":"80","action": "accept" }]}'
        #ACLs=json.loads(aclData)
        #ACLs['acls'][0]['sip']=data['ip']

       # return json.dumps(flowRules) 
        return flowRules 

    @cherrypy.expose
    def index(self): 
        return ""

if __name__ == '__main__':

    config = {'server.socket_host': '0.0.0.0',
             'server.socket_port': 8888,
             'tools.staticdir.on': True,
             'tools.staticdir.dir': "/home/twan/micronets/mud/data"}
    cherrypy.config.update(config)
   #cherrypy.quickstart(MyWebService())
    cherrypy.tree.mount(MudManagerWS())
    cherrypy.engine.start()
    cherrypy.engine.block()


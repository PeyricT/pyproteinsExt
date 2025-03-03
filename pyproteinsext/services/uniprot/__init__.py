from flask import Flask, jsonify, abort, request, jsonify, make_response
from pyproteinsext import uniprot as pExt
from .store import collectionProxy as redisCollection
from .store.collectionProxy import InsertionError
import re


UNIPROT_COLLECTION=None
# temp hack
REDIS=False

def cleanup(rh=None, rp=None):
    redisCollection.bootstrap(host=rh, port=rp)
    redisCollection.cleanup()

def startup(xmlUniprot, redis=False, rh=None, rp=None):

    global UNIPROT_COLLECTION, REDIS
   # UNIPROT_COLLECTION = pExt.EntrySet(collectionXML=xmlUniprot)
   
    if xmlUniprot:
        print(f"Loading XML ressource {xmlUniprot} ...")
        _ = pExt.EntrySet(collectionXML=xmlUniprot)
        UNIPROT_COLLECTION = _    
    if redis:
        REDIS=True
        redisCollection.bootstrap(host=rh, port=rp)        
        if xmlUniprot:
            redisCollection.convert(_)
        UNIPROT_COLLECTION = redisCollection
        
    print("Uniprot storage service listening")
 
    app = Flask(__name__)

    app.add_url_rule('/handshake', 'handshake', handshake)

    app.add_url_rule('/model', 'model', model,
                        methods = ['POST'] )
    
    app.add_url_rule( '/uniprot/<uniprotID>', 'getProtein', getProtein,
                      methods = ['GET'] ) 
    
    app.add_url_rule( '/uniprots', 'getProteins', getProteins,
                      methods = ['POST'] )

    app.add_url_rule( '/length', 'length', length,
                      methods = ['GET'] ) 
    
    app.add_url_rule( '/uniprot/list', 'list', listProtein)
    app.add_url_rule( '/uniprot/list/<interval>', 'listProtein', listProtein)
    
    app.add_url_rule('/uniprot/put', 'put', put,
                        methods = ['POST'] )
    
    app.add_url_rule('/uniprot/put_many', 'put_many', put_many,
                        methods = ['POST'] )

    app.add_url_rule('/uniprot/wipe', 'wipe', wipe,
                        methods = ['GET'] )

    #app.add_url_rule('/unigo/<taxid>', 'view_unigo', view_unigo)    

    return app

def wipe():
    redisCollection.cleanup()
    return make_response( 
        jsonify( { "operation" : "wipe", "results": "success"} )
    )
       
def put_many():
    global UNIPROT_COLLECTION
   
    if not request.is_json:
        print("Post data not json")
        abort(422)
    print('OHOH')
    data = request.get_json()
    print(f"Adding stuff log {data}")    
    ans_status = {
        "success" : [],
        "errors"  : []
    }
   
    for e in data["entrySet"]:
        try :
            UNIPROT_COLLECTION.add(e)
            ans_status["success"].append({"id":e["id"]})
        except Exception as err:
            print(f"Error in put_many:{err}")
            ans_status["errors"].append({"id":e["id"], "message" : str(err)})
            
    return { "operation" : "put_many", "results": ans_status}, \
        200

def put():
    global UNIPROT_COLLECTION
   
    if not request.is_json:
        print("Post data not json")
        abort(422)
    print('OHOH')
    data = request.get_json()
    print(f"Adding stuff log {data}")    
    try :
        UNIPROT_COLLECTION.add(data)
    except InsertionError as e:
        return make_response(jsonify( { "error" : str(e)}) , 304)
    
    return jsonify({"success": data["id"]})

def listProtein(interval=':1000'):
    def parseInterval(string): 
        """Parse a slice-like expression"""       
        m1 = re.match("^:{0,1}([\d]+)$", string)
        if m1:
            return (0, int(m1[1]))
        m2 = re.match("^:([\d]+)$", string)
        if m2:
            return (int(m2[1]), None)
        m3 = re.match("^([\d]+):([\d]+)$", string)
        if m3:
            return (int(m3[1]), int(m3[2]))
    
    cstart, cstop = parseInterval(interval)
    #print(interval, "=>", cstart, cstop)
    listIDs = redisCollection.getSliceIDs(cstart, cstop)
    
    return jsonify( {"entryIDs" : listIDs} )


def length():
    global UNIPROT_COLLECTION
    if REDIS:
        length = UNIPROT_COLLECTION.length()
    else:
        length = len(UNIPROT_COLLECTION)
    print(f"Current Collection size ${length}")
    return jsonify( {"totalEntry" : length} )

def getProtein(uniprotID):
    print(f"Seeking {uniprotID}")
    oProtein = UNIPROT_COLLECTION.get(uniprotID)
    if not oProtein:
        return make_response( jsonify( { uniprotID : "not found" }), 404 )
    return jsonify( { uniprotID : oProtein.toJSON() } )

def getProteins():
    if not request.is_json:
        print("Post data not json")
        abort(422)
    data = request.get_json()
    if not 'uniprotIDs' in data:
        print("Post data lacks uniprotIDs key")
        abort(422)
    ## implements redis
    results = {}
    validCnt = 0
    # tmp hack
    if not REDIS:
        for id in data['uniprotIDs']:
            _ = UNIPROT_COLLECTION.get(id)
            results[id] = _.toJSON() if not _ is None else None
            validCnt = validCnt + 1 if results[id] else validCnt
    else:
        print("Fetching many via redis")
        for e in UNIPROT_COLLECTION.mget(data['uniprotIDs'], raw=False):
            results[e.id] = e.toJSON() if not e is None else None
            validCnt = validCnt + 1 if results[e.id] else validCnt

    print(f"Returning { validCnt } valid elements")
    return jsonify(results)

def model():
    #pyproteinsext.model()
    return "Hello world"

def handshake():
    return 'hello'
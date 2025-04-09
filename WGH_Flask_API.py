# WarrenGHolley.com API.
###
# Mostly thrown together as a joke, as a surprising number of jobs ask for API experience.
# 

import os, sys, datetime, re, random
from flask import Flask, request, jsonify
import markupsafe  # Flask deprecated it's internal '.escape()' function.

app = Flask(__name__)
app.url_map_strict_slashes = False

# Setup all the hard-coded paths. Should really be set via args.
LOGFILE         = os.path.join( os.path.dirname( __file__ ), "Log_API.txt" ) # Should have made this an argument. Or logged to the database.
TOGGLE_LED_REQS = os.path.join( os.path.dirname( __file__ ), "Log_Requests_to_Annoy_Warren.txt" ) 
DATABASE_PATH   = os.path.join( os.path.dirname( __file__ ), "Book_Database.sqlite" )

### Sanitization ############################
@app.before_request
def clear_trailing():
  # Scrub the trailing slash if it's the last character.
  # Eg: <site>/api/Endpoint/ -> <site>/api/Endpoint
  from flask import redirect

  rp = request.path
  if rp != '/' and rp.endswith('/'):
    return redirect(rp[:-1])
    
def Sanitize_String( Unsanitized_Str ):
  # Just pushes the string through the 'markupsafe.escape' function.
  # Barely exercised, so not really certain if this is sane.
  # If it fails for any reason, just returns the raised exception.
  try:
    return markupsafe.escape( Unsanitized_Str.strip() )
  except Exception as E: 
    return "Markupsafe sanitization failed. {:s}".format(str(E))

### Logging #################################
def Log_Write( Log_String, Logfile = LOGFILE ):
  # Writes a string to a logfile.
  # UTC timestamp, whatever string it was given.
  # Does some escaping, but I've not looked into if .write has any vulns for non-escape strings.
  # Could be insufficient, could be good.
  Timestamp = datetime.datetime.now( datetime.UTC )
  Timestamp_Str = Timestamp.strftime("%Y-%m-%dT%H:%M:%SZ") # ISO-8601 is the best time format, and I will argue vehemently about it.
  
  Sanitized_Str = Sanitize_String( Log_String )
  
  with open(Logfile,'a') as FH:
    FH.write("{:s} - {:s}\n".format( Timestamp_Str, Sanitized_Str ))
   
### Database ################################

def Get_Book( Verbose=False ): # Returns a string: "{:s} - {:s}" - Title, Author.
  # Deployed code has a tiny SQLLite database.
  # Do a -dead- simple query here, but don't bother doing full sanity-check & error-handling if it explodes.
  # If the database DNE, or the format's wrong, or it's just broken fundamentally, just return a random selection from the Backup array.
  # Also note the complete lack of security.
  # Doing vulnerability analysis is -far- outside the scope of this joke.
  # Set the Verbose arg to true if you want to know what went wrong.
  
  Current_Book = None
  try: # Just do everything in a Try-Catch.
    import sqlite3
    # Path = "./Book_Database.sqlite"
    
    # ... /Fine/. Raising this exception as the current interface doesn't have a 'Don't create if DNE' flag, oddly.
    # There's an odd odd interface 'sqlite3_open_v2', but once again, far too much effort.
    if not os.path.exists( DATABASE_PATH ):
      raise OSError("Database DNE, not creating: {:s}".format( Database_Path ))
    
    # And parse the path into a URI path, as to allow a Read-Only flag.
    _Path_URI = "file:{:s}?mode=ro".format( DATABASE_PATH )
    Connection = sqlite3.connect(_Path_URI, uri=True)
    Cursor     = Connection.cursor()
    
    # Structure of 'books' table: (title, author). Strings.
    Book_List = Cursor.execute("SELECT * from books").fetchall() # Returns lists of two-element touples.
    Current_Book = random.choice(Book_List) # Just pick one touple at random.
    Current_Book = " - ".join(Current_Book) # Merge them into a single string.
    
  except Exception as E:
    # ... Something went wrong. Only print if requested.
    if Verbose: print(str(E))
  
  # Basically a 'finally' call. Do a final check if the return string is unpopulated.
  if Current_Book is None:
    Backup_List = ["Dead Beat - Jim Butcher","Skin Deep - Exchanges - Kory Bing","House of Leaves - M.Z. Danlelewski","John Dies in the End - David Wong (Jason Pargin)"]
    Current_Book = random.choice(Backup_List) # Just pick one of them at random.

  return Current_Book
  


### Actual API Nonsense #####################

@app.route("/api")
def API_This_Is_Honestly_Just_Here_Because_I_Couldnt_Find_A_Simple_Way_To_Scrub_The_Prefix_Without_Screwing_With_Logging():
  return "No redirects here. You just found the root-page of the API subsection. I should probably should make this a 404 or something."

@app.route("/api/api")
def API_Get_Whats_On_My_Table():
  # Returns a UTC Timestamp, in ISO-8601, and a random book I'm reading.
  # Or at least was on my nightstand as of when I wrote this.
  # ... House of Leaves has been there, unopened, for a while now.
  
  Current_Time = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
  Current_Book = Get_Book()

  return jsonify({ 'Current_Time_UTC':Current_Time, 'Current_Book':Current_Book })
  
@app.route("/api/message",methods=['GET','POST'])
def API_Send_Message():
  # Just a simplified method of the message request, without intentionally flashing the LED at me.
  # There's probably a better way to do the Post/Get parsing.
  if request.method=='POST': # Post is usually a wget or curl call.
    Info = request.get_json()
    Message  = Info['message']  if 'message'  in Info else None
  else: # GET, nominal HTTP request.
    Message  = request.args.get('message')
    
  # Raise an error if a string from neither method is given.
  if Message is None or Message.strip() == "":
    return "No message arg found. Is this intentional?",400
    
  # And sanitize the whole string, & write the message to the logfile.
  # Don't extract just the message.
  Requestor_IP = request.environ.get('HTTP_X_REAL_IP', request.remote_addr) # Get the IP of the requestor. (If de-proxied)
  Request_URL = request.url # Includes any args.  
  Log_Write( "{:s} {:s}".format( Requestor_IP, Request_URL ) )
  return "Message has been delivered!"

@app.route("/api/say_hi", methods=['GET','POST'])
def API_Annoy_Warren():
  # There's probably a better way to do the Post/Get parsing.
  if request.method=='POST': # Post is usually a wget or curl call.
    Info = request.get_json()
    
    Duration = Info['duration'] if 'duration' in Info else None
    Period   = Info['period']   if 'period'   in Info else None
    Message  = Info['message']  if 'message'  in Info else None
    API_Key  = Info['api_key']  if 'api_key'  in Info else None

  else: # GET, nominal HTTP request.
    Duration = request.args.get('duration')
    Period   = request.args.get('period')
    Message  = request.args.get('message')
    API_Key  = request.args.get('api_key')

  # Instantiate to strings if not given. Both above methods output None if not given.
  if Duration is None: Duration = ''
  if Period   is None: Period   = ''
  if Message  is None: Message  = ''
  if API_Key  is None: API_Key  = ''

  Duration = Duration.strip()
  Period   = Period.strip()
  Message  = Message.strip()
  
  # Log the entire request, as to sanity check at later dates.
  # Does sanitization internally.
  Request_URL = request.url # Includes any args.
  Requestor_IP = request.environ.get('HTTP_X_REAL_IP', request.remote_addr) # Get the IP of the requestor. (If de-proxied)
  Log_Write( "{:s} {:s}".format( Requestor_IP, Request_URL ) )
  
  
  # And do sanity checks as to make sure everything's parsed correctly.
  # API return-strings -shouldn't- need sanitization? Logging & databases are the primary vulns for injection.
  if   Duration == '' and Period == '': return "It appears neither 'period' nor 'duration' arg was given?", 400
  elif Duration == '':                  return "The 'duration' arg appears to be empty!", 400
  elif Period == '':                    return "The 'period' arg appears to be empty!", 400

  # Attempt parsing - Do initial format sanity checks.
  if not re.search( r'^\d+[a-zA-Z]$', Duration ): return "The 'duration' arg given '{:s}' doesn't appear to have a \\d+\\c structure!".format(Duration), 400
  if not re.search( r'^\d+[a-zA-Z]$', Period   ): return   "The 'period' arg given '{:s}' doesn't appear to have a \\d+\\c structure!".format(Period), 400

  # Check that the unit makes sense.
  if not Duration[-1] in 'hms': return "The unit given for Duration '{:s}' needs to be either 'h', 'm', or 's'.".format( Period[-1] ), 400
  if not Period[-1] in 'hms':   return "The unit given for Period '{:s}' needs to be either 'h', 'm', or 's'.".format( Period[-1] ), 400

  if int(Duration[:-1]) == 0:
    return "The 'duration' time given '{:s}' parses to zero seconds. This would only be visible in the logs, and won't succuessfully anno---- let Warren know you're saying 'Hi'!".format(Duration), 400

 
  # I've not tested if theres a limit on POST/GET string sizes. Lol.
  # I'm leaving this in as an invite to crash my API, or fill up the filesystem. Praise be to Chaos.
  _Toggle_LED_Request_Str = "{:s} {:s} {:s} {:s}".format( Requestor_IP, Duration, Period, Message )
  Log_Write( _Toggle_LED_Request_Str, Logfile=TOGGLE_LED_REQS )
  # The ToggleLED script parses the Requests logfile. Just time, Duration, Message. Should be parsing safe.

  return "You've successfully poked Warren. If he's AFK, he'll see it in the logs."


# Note that this isn't run when run through the WSGI of GUnicorn.
# Needs testing on nginx's built-in equivalent.
if __name__ == "__main__":
  app.run(debug=True)

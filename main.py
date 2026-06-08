
# Interal Libraries
import logging
import datetime
import os
import random
import sqlite3

# External Libraries
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.responses import StreamingResponse
from fastapi.responses import RedirectResponse

# Library Modules Config:
logging.basicConfig(
    filename="API_Logfile.txt",
    filemode='w', # Just overwrite the file on restart. Needs an upgrade for safe archiving.
    level= logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S", # ISO8601 is the best time format, and I -will- fight about it. Doesn't allow microsecond %f flag?
)
logger = logging.getLogger( __name__ )

app = FastAPI()

# Constants:
DATABASE_PATH = os.path.join( os.path.dirname( __file__ ), "Book_Database.sqlite" )

######
# Summary, as I'm not too well versed in writing APIs. (And this is mostly a joke)
# api.wgh.com gets redirected here.
# /  (root)     -> Redirect to api.wgh.com/docs
# /send_message -> Saves Timestamp, IP, and message to a file that I monitor.
# /blinkenlight -> Blink

# TODO:
# Dig further into the FastAPI Request docs.
# - Not sure request.client.host is the best or safest way to get the user's IP.

@app.get("/") # Redirects to the root https://api.warrengholley.com/docs
async def redirect_to_docs( request: Request ) -> RedirectResponse:
    logger.info("{:s} - Redirected to Docs".format(request.client.host))
    #return RedirectResponse("https://api.warrengholley.com/docs")
    return RedirectResponse(url='/docs')

@app.get("/send_message") # Returns CSV, confirming message.
def api_say_hi( message: str, request: Request ) -> str:
    logger.info("{:s} - Message: '{:s}'".format(request.client.host, message))
    return "The message has been logged!"

@app.get("/blinkenlight", response_class=PlainTextResponse) # Returns CSV, confirming blinking.
def api_blinkenlight( duration:  int,
                      frequency: int,
                      request:   Request  ) -> str:
    # Logs enough data for an on-prem Raspberry Pi to read a
    logger.info("{:s} - Blinken: {:d}s {:d}s".format(request.client.host, duration, frequency))

    # Set up a lamba funtion (needlessly fancy), to bind the range of the inputs.
    # FastAPI does all the type-checking, which simplifies things greatly.
    range_limit = lambda inval, minval, maxval: max(min(maxval, inval), minval)
    
    # Bind each to the limits of the range.
    sanitized_duration  = range_limit( duration,  0, 60 )
    sanitized_frequency = range_limit( frequency, 0,  5 )

    std_message  = "The LED is blinking, and this interaction has been logged!\n"

    # Poke fun at the user if they try to give silly numbers.
    error_message = ""
    if sanitized_duration != duration:
        error_message += "Duration bound from {:d} to {:d} seconds.\n".format(duration, sanitized_duration)
    if sanitized_frequency != frequency:
        error_message += "Frequency bound from {:d} to {:d} seconds.\n".format(frequency, sanitized_frequency)
   
    if error_message != "":
        return std_message + "\n\n" + error_message
       
    return std_message

@app.get("/database_query")
def API_Get_Whats_On_My_Table( request: Request ):
  # Returns a UTC Timestamp, in ISO-8601, and a random book I'm reading.
  # Or at least was on my nightstand as of when I wrote this.
  # ... House of Leaves has been there, unopened, for a while now.
  #####
  # Deployed code has a tiny SQLLite database.
  # Do a -dead- simple query here, but don't bother doing full sanity-check & error-handling if it explodes.
  # If the database DNE, or the format's wrong, or it's just broken fundamentally, just return a random selection from the Backup array.
  # Also note the complete lack of security.
  # Doing vulnerability analysis is -far- outside the scope of this joke.
  # Set the Verbose arg to true if you want to know what went wrong.
  logger.info("{:s} - BookFetch".format(request.client.host))

  Current_Book = None
  try: # Just do everything in a Try-Catch.
    # Path = "./Book_Database.sqlite"
    
    # ... /Fine/. Raising this exception as the current interface doesn't have a 'Don't create if DNE' flag, oddly.
    if not os.path.exists( DATABASE_PATH ):
      raise OSError("Database DNE, not creating: {:s}".format( DATABASE_PATH ))
    
    # And parse the path into a URI path, as to allow a Read-Only flag.
    _Path_URI = "file:{:s}?mode=ro".format( DATABASE_PATH )
    Connection = sqlite3.connect(_Path_URI, uri=True)
    Cursor     = Connection.cursor()
    
    # Structure of 'books' table: (title, author). Strings.
    Book_List = Cursor.execute("SELECT * from books").fetchall() # Returns lists of two-element touples.
    Current_Book = random.choice(Book_List) # Just pick one touple at random.
    Current_Book = " - ".join(Current_Book) # Merge them into a single string.
    
  except Exception as E:
    logger.info("{:s} - BookFetch Exception {:s}".format(request.client.host, str(E)))
  
  # Basically a 'finally' call. Do a final check if the return string is unpopulated.
  if Current_Book is None:
    Backup_List = ["Dead Beat - Jim Butcher","Skin Deep - Exchanges - Kory Bing","House of Leaves - M.Z. Danlelewski","John Dies in the End - David Wong (Jason Pargin)"]
    Current_Book = random.choice(Backup_List) # Just pick one of them at random.

  # And then serialize to JSON.
  Current_Time = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

  Return_Block = {'Current_Time_UTC':Current_Time, 'Current_Book':Current_Book }

  return Return_Block # Returns as json.
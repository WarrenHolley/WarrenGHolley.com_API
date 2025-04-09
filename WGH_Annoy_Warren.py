# The standalone interface to the /say_hi API interface.
# Runs as a service on the same sandboxed RPi that runs the website.
# When a request is made, it writes the sanitized request to a hardpathed logfile.
# This is read, each request processed.
# A file-based comms system was the easiest solution to request-queueing.

#import RPi.GPIO as GPIO
import os, sys, datetime
import time
import shutil

# Global Constants.
IN_FILE = os.path.join( os.path.dirname( __file__ ), "Log_Requests_to_Annoy_Warren.txt" ) 
GPIO_PIN = 4 # Uses GPIO4, or, from the pinout, pin 7.

# Global Variables
LAST_REQUEST_TIME = datetime.datetime.now( datetime.UTC ).replace(tzinfo=None) - datetime.timedelta(hours=1)
# The runtime of the last query, as to maintain the queue. Assumes downtime is an hour, in the event of a reboot or restart.
# Could upgrade to use a file-saved timestamp or even use the Book_Database.
# Forces the timestamp into a UTC timestamp, then scrubs the timezone component as to not deal with the comparator constraints.
CURRENT_REQUESTS = [] # List of <DT, Dur, Period>, as read by Read_Requests_File
# Populated & used in Get_Next_Requests as to handle the requests.


### SETUP & GPIO USAGE ########################
def Setup_GPIO():
  # Just set up all the args required.
  GPIO.setmode( GPIO.BCM)
  GPIO.setup  ( GPIO_PIN, GPIO.OUT) # Set the pin to -output-.
  GPIO.output ( GPIO_PIN, GPIO.LOW) # Defaults to being -on-, which is fine, but I'd rather have all the active control in the actual trigger code below, rather than relying it be on.

  import atexit
  atexit.register( GPIO.cleanup )
  # And always run the GPIO.cleanup func regardless of if the program completed.
  # Failure to do so throws up annoying errors.

def Flash_LED( ms_Duration, ms_Period ):
  # ... Could actually upgrade this to do PWM. Do On-time/Off-time instead. TODO?
  ms_remaining = ms_Duration

  while ms_remaining > 0:
    GPIO.output( GPIO_PIN, GPIO.HIGH )
    time.sleep ( ms_Period / 2000    ) # Needs a float of seconds to sleep for. Sleep for half the duration of the period.

    GPIO.output( GPIO_PIN, GPIO.LOW  )
    time.sleep ( ms_Period / 2000    )

    # And decrement the remaining time.
    ms_remaining -= ms_Period
    # Could be more accurately improved by using the time.clock_gettime_ns(), but that might make this joke look too professional.
  return

### File Handling ##############################
def Read_Requests_File( Path=IN_FILE ):
  # Returns <Timestamp, Dur, Period>
  # Timestamp is UTC Datetime object.
  # Duration & Period are integer milliseconds.
  # Couple of possible excetions could be thrown here. Don't catch them here.
  
  Data = [Line.strip() for Line in open(IN_FILE,'r').readlines() if Line.strip() != ""]

  # And parse.
  # Example line: "2025-04-09T05:27:25Z - 127.0.0.1 5s 5s Random Message\n" # Timestamp, IP, Duration, Period, Message
  Timestamp_Str = [ Line.split()[0] for Line in Data ]
  Duration      = [ Line.split()[3] for Line in Data ]
  Period        = [ Line.split()[4] for Line in Data ]

  # Translate the timestamp into a dt object.
  UTC_DT   = [ datetime.datetime.strptime( dt_str, "%Y-%m-%dT%H:%M:%SZ" ) for dt_str in Timestamp_Str ]
  # Parse everything into milliseconds.
  Duration = [ _Translate_To_Milliseconds( Dur_Str ) for Dur_Str in Duration ]
  Period   = [ _Translate_To_Milliseconds( Per_Str ) for Per_Str in Period   ]
  
  # And make sure that nothing is longer than 5m. Don't wan't any idiot requsting they annoy me until the heat death of the universe.
  Duration = [ min(dur, 5*60*1000) for dur in Duration ]
  Period   = [ min(per, 5*60*1000) for per in Period   ]
  
  # And stack.
  Out_Array = [ [UTC_DT[i],Duration[i],Period[i]] for i in range(len( UTC_DT )) ]
  return Out_Array

def _Translate_To_Milliseconds( Arg ):
  # Given a \d\c string, return milliseconds.
  # Eg: 2h = 120m = 7200s =  7,200,000ms
  # Assume it's sanity checked in the Flask app, as that's the side facing the monkeys with keyboards.
  _Val  = int(Arg[:-1])
  _Mult = Arg[-1]

  if   _Mult == 'h': return _Val * 60*60*1000
  elif _Mult == 'm': return _Val *    60*1000
  elif _Mult == 's': return _Val *       1000
  else:
    Log_Write( "Given arg {:s}. Uncaught until Toggle_LED".format(Arg) )
    raise ValueError("{:s} did not parse correctly. Logging to diagnose why this wasn't caught before Toggle_LED.".format(Arg))

def Archive_File( Filepath ):
  # If there's an issue with the current Request File, archive it in it's entirety.
  # Just renames it to Filepath+".{:03d}.archive", where the number auto-increments to the lowest unpopulated value.
  
  # Get the current file listings.
  Current_Files = [ Name for Name in os.listdir( os.path.dirname(__file__)) if Name.endswith(".archive") ]
  Current_IDs   = [ int(Name.split(".")[-2]) for Name in Current_Files ] # Really needs some sanity checks.
  if len(Current_IDs) == 0:
    Next_ID = 0
  else:
    Next_ID = max(Current_IDs) + 1
  
  Archive_Filepath = "{:s}.{:03d}.archive".format(Filepath, Next_ID) # Includes the leading path if given
  shutil.move( Filepath, Archive_Filepath )  


### Request Handling ##############################
def Reload_Current_Requests( Input_Path=IN_FILE, Min_Time=LAST_REQUEST_TIME ):
  # Reads the CURRENT_REQUESTS lists.
  # Truncates the list on the input time as to limit the requests size.
  # If there's an issue reading the file, then archive it.
  global CURRENT_REQUESTS
  # Check that the file actually exists. If not, then clear out the array, return.
  if not os.path.exists( Input_Path ):
    print("File DNE: {:s}".format(Input_Path) )
    CURRENT_REQUESTS = []
    return
  # Otherwise, read the file.
  try:
    _Temp_List = Read_Requests_File( Input_Path )
    # Filter on the timestamp.
    Future_Requests = [ [Time,Dur,Per] for Time,Dur,Per in _Temp_List if Time > LAST_REQUEST_TIME ]
    CURRENT_REQUESTS = Future_Requests
    return
    
  except Exception as E: # Catch any file-reading errors, likely.
    # Archive the file as needed.
    print("Issue in repopulating Current_Requests: {:s}".format(str(E)))
    print("Archiving File...")
    Archive_File( Input_Path )
    # Then clear out the array & return.
    CURRENT_REQUESTS = []
    return
  
def Get_Next_Request():
  # Handler for the global CURRENT_REQUESTS.
  # Keys off of, and updates LAST_REQUEST_TIME as needed.
  # Returns None if there's nothing in the list, otherwise returns a two-element touple of the next Duration & Period.
  global LAST_REQUEST_TIME
  
  # Try to reload the requestlist if it's not populated.
  # If it's populated, but there's nothing left in the list after the LAST_REQUEST_TIME filter, then reload.
  if         CURRENT_REQUESTS is None \
    or   len(CURRENT_REQUESTS) == 0   \
    or ( len(CURRENT_REQUESTS) >  0 and CURRENT_REQUESTS[-1][0] <= LAST_REQUEST_TIME ):
    Reload_Current_Requests( IN_FILE, LAST_REQUEST_TIME )

  # And if it's still empty, return the None sleep condition. It's either failed, or there's nothing in the list.
  if len(CURRENT_REQUESTS) == 0:
    return None
   
  # If it's populated, just return the next Duration,Period pair in the queue.
  # Filter for the remaining requests.
  Remaining_Requests = [ [Timestamp, Duration, Period] for Timestamp, Duration, Period in CURRENT_REQUESTS if Timestamp > LAST_REQUEST_TIME ]
  
  # If there are none remaining, return the None sleep condition.
  if Remaining_Requests == []: return None
    
  # Otherwise, return the most recent entry, update the LAST_REQUEST_TIME timestamp.
  Remaining_Requests.sort() # Sanity check. Sorts by the first element (Time).
  Time, Dur, Per = Remaining_Requests[0]
    
  LAST_REQUEST_TIME = Time
  return (Dur, Per) # Milliseconds.    

### MAIN ################################
def Main():
  # Do all the setup.
  Setup_GPIO()

  while True: # Infinite Loop.
    # Read the input file. If there's nothing, returns None as a sleep condition flag.
    # Otherwise, returns a touple of milliseconds of Duration & Period to run the Flash-Lights-At-Warren protocol at me.
    Next_Request = Get_Next_Request() # Reads the requests file. If nothing, returns None. 

    if Next_Request is None:
      print("sleeping")
      time.sleep(10) # Sleep for 10s, then continue.
      continue
    
    Duration_ms, Period_ms = Next_Request # Explode the touple.
    Annoy_Warren( Duration_ms, Period_ms)


if __name__ == "__main__":
  if len(sys.argv) == 1:
    print("Called without args. I should write a helpfile.")
    sys.exit()
  elif sys.argv[1] == '--daemon':
    Main() # Runs it in Daemon/Server mode.
  # The flag was picked as to allow expandability.
  # I had a CLI-log-append method here before, but decided to pawn that off to the Flask API call.

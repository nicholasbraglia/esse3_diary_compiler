import os
import datetime
import logging
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

def calculate_duration_hours(start_dict, end_dict, default_all_day_hours=8.0):
    if 'date' in start_dict and 'date' in end_dict:
        start_date = datetime.date.fromisoformat(start_dict['date'])
        end_date = datetime.date.fromisoformat(end_dict['date'])
        days = (end_date - start_date).days
        if days < 1:
            days = 1
        return float(default_all_day_hours) * days
    start_str = start_dict.get('dateTime')
    end_str = end_dict.get('dateTime')
    if start_str and end_str:
        start_str = start_str.replace('Z', '+00:00')
        end_str = end_str.replace('Z', '+00:00')
        start_dt = datetime.datetime.fromisoformat(start_str)
        end_dt = datetime.datetime.fromisoformat(end_str)
        delta = end_dt - start_dt
        return round(delta.total_seconds() / 3600, 2)
    return 0.0

def get_google_flow(redirect_uri, state=None):
    """Creates and returns the Google Flow object in a single step."""
    return Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=redirect_uri
    )

def generate_auth_url(redirect_uri):
    flow = get_google_flow(redirect_uri)
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    return authorization_url, state, flow.code_verifier

def fetch_google_credentials(redirect_uri, state, code_verifier, authorization_response):
    flow = get_google_flow(redirect_uri, state=state)
    flow.code_verifier = code_verifier
    flow.fetch_token(authorization_response=authorization_response)
    creds = flow.credentials
    return {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }

def get_events(creds_dict, start_date, end_date):
    credentials = Credentials(**creds_dict)
    service = build('calendar', 'v3', credentials=credentials)

    start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d").isoformat() + 'Z'
    end_dt = (datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)).isoformat() + 'Z'

    raw_events = []
    calendars_result = service.calendarList().list().execute()
    calendars = calendars_result.get('items', [])

    for calendar in calendars:
        calendar_id = calendar['id']
        
        try:
            events_result = service.events().list(
                calendarId=calendar_id, 
                timeMin=start_dt, 
                timeMax=end_dt,
                singleEvents=True, 
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            raw_events.extend(events)
            
        except HttpError as error:
            logger.error(f'Errore API Google Calendar: {error.reason}')
            raise error

    raw_events.sort(key=lambda x: x.get('start', {}).get('dateTime', x.get('start', {}).get('date', '')))
    return raw_events


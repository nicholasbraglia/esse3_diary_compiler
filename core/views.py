import os
import datetime
import logging
from django.shortcuts import render, redirect
from django.urls import reverse

from .services.Esse3Automator import execute_diary_sync, _fill_diary_hours
from .services import google_calendar_service
from googleapiclient.errors import HttpError

import time
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

from .services.classifier import ClassifierEsse3

logger = logging.getLogger(__name__)


# --- VIEWS ---
def dashboard(request):
    return render(request, 'core/dashboard.html')


def google_login(request):
    # Early return: if it is not a POST request, return immediately
    if request.method != 'POST':
        return redirect('dashboard')

    request.session.update({
        'start_date': request.POST.get('start_date'),
        'end_date': request.POST.get('end_date')
    })

    redirect_uri = request.build_absolute_uri(reverse('google_callback'))
    authorization_url, state, code_verifier = google_calendar_service.generate_auth_url(redirect_uri)

    request.session.update({
        'state': state,
        'code_verifier': code_verifier
    })

    return redirect(authorization_url)


def google_callback(request):
    if 'error' in request.GET:
        error_msg = request.GET.get('error')
        return render(request, 'core/dashboard.html', {
            'success': False,
            'message': 'Accesso a Google negato o interrotto',
            'errors': [f'Dettaglio: {error_msg}. Per usare il sistema devi autorizzare l\'accesso al calendario.']
        })

    try:
        state = request.session.get('state')
        if not state:
            raise ValueError("Sessione di login scaduta. Riprova.")

        redirect_uri = request.build_absolute_uri(reverse('google_callback'))
        code_verifier = request.session.get('code_verifier')
        authorization_response = request.build_absolute_uri()

        creds_dict = google_calendar_service.fetch_google_credentials(
            redirect_uri, state, code_verifier, authorization_response
        )

        request.session['google_creds'] = creds_dict
        
        return redirect('loading_preview')

    except Exception as e:
        return render(request, 'core/dashboard.html', {
            'success': False,
            'message': 'Errore durante la comunicazione con Google 🔌',
            'errors': [
                'Non è stato possibile completare lo scambio del token.', 
                f'Dettaglio tecnico: {str(e)}'
            ]
        })


def loading_preview(request):
    """Mostra istantaneamente una pagina di caricamento prima di interrogare l'IA."""
    return render(request, 'core/loading.html')


def preview_matrix(request):
    creds_dict = request.session.get('google_creds')
    start_date = request.session.get('start_date')
    end_date = request.session.get('end_date')

    if not creds_dict or not start_date or not end_date:
        return redirect('dashboard')

    try:
        raw_events = google_calendar_service.get_events(creds_dict, start_date, end_date)

        # 3. Classification
        classifier = ClassifierEsse3()
        valid_categories = classifier.valid_categories

        processed_events = []
        for idx, item in enumerate(raw_events):
            title = item.get('summary', 'Senza Titolo')
            start_dict = item.get('start', {})
            end_dict = item.get('end', {})

            duration = google_calendar_service.calculate_duration_hours(start_dict, end_dict)
            raw_start_date = start_dict.get('dateTime', start_dict.get('date', ''))
            print(raw_events)
            pure_date = raw_start_date[:10] if raw_start_date else "N/A"
            print(pure_date)

            categoria, metodo = classifier.classify(title)

            processed_events.append({
                'id': idx,
                'title': title,
                'date': pure_date,
                'duration': duration,
                'category': categoria,
                'method': metodo
            })

        return render(request, 'core/preview.html', {
            'events': processed_events,
            'categories': valid_categories
        })

    except HttpError as error:
        # Catches errors in Google’s APIs
        return render(request, 'core/dashboard.html', {
            'success': False,
            'message': 'Errore di comunicazione con Google Calendar',
            'errors': [f'Errore API: {error.reason}']
        })

    except Exception as e:
        return render(request, 'core/dashboard.html', {
            'success': False,
            'message': 'Errore imprevisto durante l\'analisi degli eventi',
            'errors': [str(e)]
        })


def sync_esse3(request):

    if request.method == 'POST':
        username = request.POST.get('esse3_username')
        password = request.POST.get('esse3_password')
        raw_otp_seed = request.POST.get('esse3_otp')
        clean_otp = raw_otp_seed.replace(' ', '').replace('-', '').upper()

        matrix_esse3 = {}

        # The form in preview.html submits fields such as ‘date_0’, “duration_0” and ‘category_0’
        for key in request.POST:
            if key.startswith('date_'):
                event_id = key.split('_')[1]

                category_val = request.POST.get(f'category_{event_id}')

                if category_val in ('ignore', 'Da non considerare') or not category_val:
                    continue

                # Retrieving the values associated with this event
                date_val = request.POST.get(f'date_{event_id}')
                duration_val = float(request.POST.get(f'duration_{event_id}', 0.0))

                if date_val not in matrix_esse3:
                    matrix_esse3[date_val] = {}
                if category_val not in matrix_esse3[date_val]:
                    matrix_esse3[date_val][category_val] = 0.0

                matrix_esse3[date_val][category_val] += duration_val

        risultato = execute_diary_sync(matrix_esse3, username, password, clean_otp)

        context = {
            'message': risultato.get('message', 'Operazione completata.'),
            'success': risultato.get('success', False),
            'errors': risultato.get('errors', [])
        }
        return render(request, 'core/dashboard.html', context)

    return redirect('dashboard')


def run_local_selenium_test(file_path, esse3_matrix):
    """Inizializza il driver locale e invoca la funzione importata."""
    print("\nAvvio di Chrome per il test locale...")
    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 10)

    try:
        print(f"Caricamento file HTML: {file_path}")
        driver.get(f"file:///{file_path}")
        time.sleep(2)

        print("\nPassaggio dei dati alla funzione _fill_diary_hours...")
        risultato = _fill_diary_hours(driver, wait, esse3_matrix)

        print(f"\nEsito test: {risultato.get('message')}")
        print("Chiusura browser in 5 secondi...")
        time.sleep(5)

        return risultato

    except Exception as e:
        print("Errore nel test")
        return {
            'success': False,
            'message': 'Errore durante il test',
            'errors': [str(e)]
        }


    finally:
        driver.quit()

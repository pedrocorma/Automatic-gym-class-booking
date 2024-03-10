from playwright.sync_api import Playwright, sync_playwright, expect
from time import sleep, time
from twocaptcha import TwoCaptcha
from pytz import timezone
from datetime import datetime, timedelta
import pandas as pd
import os
from dotenv import load_dotenv

##################################################################################
# 1. FUNCIONES
##################################################################################
# 1.1 Carga variables entorno
def load_env_vars():
    load_dotenv()
    creds = os.getenv('creds').split(',')
    captcha_api_key = os.getenv('captcha_api_key')
    return creds, captcha_api_key

# 1.2 Creación del dataframe nth para los selectores
def create_df_nth(df_horario):
    df_nth_tmp = pd.DataFrame()
    for hora in df_horario["HORA"].unique():
        df_tmp = df_horario.loc[df_horario["HORA"]==hora]
        lista_horario_tmp = df_tmp.iloc[::,1:].values.ravel()
        df_cumcount = pd.DataFrame(lista_horario_tmp,columns=['column']).groupby('column').cumcount(ascending=True).values.tolist()
        list_of_lists_tmp = [df_cumcount[x:x+7] for x in range(0, len(df_cumcount), 7)]
        df_tmp = pd.DataFrame(list_of_lists_tmp)
        df_nth_tmp = pd.concat([df_nth_tmp,df_tmp])
    df_nth = df_horario.copy()
    df_nth.iloc[:,1:] = df_nth_tmp
    return df_nth

# 1.3 Obtención de los parámetros del locator (texto, nth)
def locator_text_nth(clase, dia, hora_inicio, df_tm_clases, df_tm_horario):
    # Locator text
    duracion = int(df_tm_clases.loc[df_tm_clases["DES_CLASE"] == clase]["NUM_DURACION_MIN"].values[0])
    hora_fin = datetime.strptime(hora_inicio,"%H:%M") + timedelta(minutes = duracion)
    locator_text = clase + ' ' + hora_inicio + ' - ' + hora_fin.strftime('%H') + ':'  
    # Locator nth
    column_index = df_tm_horario.columns.tolist().index(dia)
    row_index = df_tm_horario.loc[(df_tm_horario[dia]==clase) & (df_tm_horario["HORA"]==hora_inicio)][dia].index[0]
    df_nth = create_df_nth(df_tm_horario)
    locator_nth = df_nth.iloc[row_index,column_index]
    return locator_text, locator_nth

# 1.4 Log datetime ejecucion
def log_time():
    log_time = datetime.now(timezone('Europe/Madrid')).strftime('%Y-%m-%d-%H:%M:%S')
    return log_time

# 1.5 Solver de captcha
def captcha_solver(api_key, url, sitekey):
    start_time = time()
    solver = TwoCaptcha(api_key)
    try:
        response = solver.recaptcha(sitekey=sitekey, url=url)
    except Exception as e:
        print(log_time(),': ',e)
    else:
        captcha_code = response['code']
        execution_time = round(time() - start_time)
        print(log_time(),f": Captcha resuelto correctamente tras {execution_time} s.")
        return captcha_code

# 1.6 Logeo en la web
def login(user, password, captcha_api_key):
    url_login = "https://cddenia.virtuagym.com/"
    # login
    print(log_time(),f': Iniciando sesión ({user}) ...')
    page.goto(url_login)
    page.get_by_label("Correo electrónico").fill(user)
    page.get_by_label("Contraseña").fill(password)
    # captcha
    print(log_time(),': Resolviendo captcha...')
    sitekey = page.locator('xpath=//*[@id="login_form"]/div[4]/div/div').get_attribute('data-sitekey')
    page.evaluate('() => document.getElementById("g-recaptcha-response").style.display = "";')
    captcha_response = captcha_solver(captcha_api_key, url_login, sitekey)
    page.locator("#g-recaptcha-response").fill(captcha_response)
    #sleep(10)
    # inicio sesion
    page.get_by_role("button", name="Iniciar sesión").click()
    print(log_time(),f': Sesión iniciada.')
    
# 1.7 Reserva de clase
def reservar_clase(clase, dia, hora_inicio, dia_ejecucion_reserva, df_tm_clases, df_tm_horario):
    print(log_time(),f': Reservando {clase} el {dia} a las {hora_inicio}...')
    url_horario_clases = "https://cddenia.virtuagym.com/classes/week/" + dia_ejecucion_reserva
    page.goto(url_horario_clases)
    #page.get_by_role("link", name="Horario", exact=True).click()
    locator_text, locator_nth = locator_text_nth(clase, dia, hora_inicio, df_tm_clases, df_tm_horario)
    page.get_by_text(locator_text).nth(locator_nth).click()
    page.get_by_role("button", name="Reservar ya").click()
    page.get_by_text(locator_text).nth(locator_nth).click()
    print(log_time(),': Clase reservada.')
    #page.get_by_text("Has reservado").click()

# 1.8 Logout
def logout(user):
    print(log_time(),f': Cerrando sesión ({user}) ...')
    url_logout = 'https://cddenia.virtuagym.com/'
    page.goto(url_logout)
    page.locator("#user-menu").get_by_role("img").click()
    page.get_by_role("link", name="Cerrar sesión").click()
    print(log_time(),': Sesión cerrada.')

##################################################################################
# 2. PARÁMETROS DE ENTRADA
##################################################################################
# 2.1 Datos de la reserva a realizar
df_tprm_reservas = pd.read_excel('GYM_TPRM_RESERVAS.xlsx')
clase = df_tprm_reservas["CLASE"].values[0]
dia = df_tprm_reservas["DIA"].values[0]
hora_inicio = df_tprm_reservas["HORA_INICIO"].values[0]

# 2.2 Dataframe maestro clases
df_tm_clases = pd.read_excel('GYM_TM_CLASES.xlsx')

# 2.3 Dataframe maestro horario
df_tm_horario = pd.read_excel('GYM_TM_HORARIO.xlsx',dtype={'HORA':str}).fillna('NULL')
df_tm_horario["HORA"] = [':'.join(x.split(':')[:2]) for x in df_tm_horario["HORA"]]

##################################################################################
# MAIN
##################################################################################
print(36*'*' + '\n' + 'SCRIPT RESERVA CLASES GYM INICIADO' + '\n' + 36*'*')

dia_ejecucion_reserva = (datetime.now(timezone('Europe/Madrid')) + timedelta(days=1)).strftime('%Y-%m-%d')

with sync_playwright() as playwright:
    # Carga variables entorno
    creds,captcha_api_key =  load_env_vars()
    
    # Playwright setup
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(locale="es")
    page = context.new_page()

    # Login + Reserva clase + Logout para todos los users
    for cred in creds:
        print(21*'-')
        # Carga creds
        user = cred.split('__')[0]
        password = cred.split('__')[1]

        # Login + Reserva + Logout
        login(user, password, captcha_api_key)
        reservar_clase(clase, dia, hora_inicio, dia_ejecucion_reserva, df_tm_clases, df_tm_horario)
        logout(user)

    context.close()
    browser.close()

print(36*'*' + '\n' + 'SCRIPT RESERVA CLASES GYM FINALIZADO' + '\n' + 36*'*')
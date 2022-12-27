# import MySQLdb
import traceback
import pyodbc 
import os
import random

DB_HOST = 'SERVER2012\PARADIGMA' 
DB_USER = 'Admin' 
DB_PASS = 'adm007bb' 
DB_NAME = 'CM030822MAW' 

def run_query(query=''): 
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+DB_HOST+';DATABASE='+DB_NAME+';UID='+DB_USER+';PWD='+DB_PASS)
        with conn.cursor() as cursor:
            cursor.execute(query)
            data = cursor.fetchone()[0]
            data = data.strip()
        return data
    except Exception as e:
        print(query)
        traceback.print_exc()
        pass

def findCode(file):
    code = ''
    count = 0
    for char in file:
        if char=='_':
            count+=1
        elif count == 2:
            code += char
    return code


def randomString():
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    random_str = ''
    for i in range(1, 5):
        random_str += chars[random.randint(0, len(chars)-1)]
    return random_str

def renameFiles():
    images_counter = 0
    path = 'C:/Users/DESA07/Desktop/script python/Imagenes/'
    for file in os.listdir(path):
        if file.upper().endswith(('JPG','JPEG', 'PNG')):
            try:
                name, extension = os.path.splitext(file)
                code = findCode(file)
                query = f'SELECT codSIGE FROM Articulos WHERE Id = {code};'
                codSIGE = run_query(query)
                print('Renombrando archivo: ', file)
                if os.path.exists(path + codSIGE + extension):
                    os.rename(path + file, path + codSIGE + '_' + randomString() + extension)
                else:
                    os.rename(path + file, path + codSIGE + extension)
            except Exception as e:
                traceback.print_exc()
                pass
            images_counter += 1
    print(f'Se actualizó el nombre de {images_counter} imágenes.')            

renameFiles()
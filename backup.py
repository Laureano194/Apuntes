import subprocess, datetime, os, shutil

def get_database_info():
    records, _ = subprocess.Popen(['sudo', '-u', 'postgres', 'psql', '-lA', '-F\x02', '-R\x01'], stdout=subprocess.PIPE).communicate()
    records = records.split('\x01')
    header = records[1].split('\x02')
    return [dict(zip(header,line.split('\x02'))) for line in records[2:-1]]

def get_backup_name(database_name):
    today = datetime.datetime.today().strftime("%d%m%y")
    return '%s/%s_%s.bak' % (datetime.datetime.today().strftime("%m_%y"), datetime.datetime.today().strftime("%d%m%y"), database_name)

def create_folder_if_not_exists():
   directory = datetime.datetime.today().strftime("%m_%y")
   if not os.path.exists(directory):
      delete_old_backups()
      os.makedirs(directory)

def delete_old_backups():
   three_months_ago = datetime.datetime.today() - datetime.timedelta(days=90)
   backup_folder = three_months_ago.strftime("%m_%y")
   if os.path.exists(backup_folder):
      shutil.rmtree(backup_folder)

def main(**kwargs):
   databases = get_database_info()
   for db in databases:
      if 'Name' in db and db['Name'] not in ['postgres', 'template0', 'template1']:
         create_folder_if_not_exists()
         backup_name = get_backup_name(db['Name'])
         command = 'sudo -u postgres pg_dump %s > %s' % (db['Name'], backup_name)
         subprocess.call([command], shell=True)

main()


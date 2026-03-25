from BaseXClient import BaseXClient
import subprocess

basex_bat = r"C:\Program Files (x86)\BaseX\bin\basexserver.bat"
subprocess.Popen([basex_bat], shell=True)

# create session
session = BaseXClient.Session('localhost', 1984, 'admin', 'admin')

try:
    # create new database
    session.create("database", "<x>Hello World!</x>")
    print(session.info())

    # run query on database
    print("\n" + session.execute("xquery doc('database')"))

    # drop database
    session.execute("drop db database")
    print(session.info())

finally:
    # close session
    if session:
        session.close()
    subprocess.run([basex_bat, "stop"], shell=True)
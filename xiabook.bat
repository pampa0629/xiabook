cd C:\zengzm\GitHub\xiabook
python C:\zengzm\GitHub\pyinstaller-develop\pyinstaller.py  -F  C:\zengzm\GitHub\xiabook\xiabook.py
xcopy C:\zengzm\GitHub\pyinstaller-develop\xiabook\dist\xiabook.exe  /e /Y C:\zengzm\GitHub\xiabook\
"C:\Program Files (x86)\WinRAR\rar"  a xiabook.rar  xiabook.exe xiabook.py conf.ini readme.txt
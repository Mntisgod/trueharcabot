mkdir -p gspread/python
cd gspread/python
pip install gspread -t .
pip install oauth2client -t .
# ※秘密鍵（JSONファイル）もこのディレクトリに格納する
cd ..
zip -r gspread.zip ./python
# =================================================================
#   A.R.I.S.E. - WSGI Entry Point
#   Used by production WSGI servers (Waitress, Gunicorn, etc.)
#
#   Usage:
#     Windows:  waitress-serve --host=0.0.0.0 --port=5000 wsgi:app
#     Linux:    gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
# =================================================================

from server import app

if __name__ == '__main__':
    app.run()

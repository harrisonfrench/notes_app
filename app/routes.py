from flask import render_template, redirect, url_for
from . import app

@app.route('/')
def index():
    # Redirect to the notes app
    return redirect(url_for('notes.index'))

@app.route('/about')
def about():
    return render_template('about.html')

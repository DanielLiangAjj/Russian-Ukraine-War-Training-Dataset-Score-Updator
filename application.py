from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql.cursors
from werkzeug.security import generate_password_hash, check_password_hash
from newsplease import NewsPlease
import logging
logging.basicConfig(level=logging.DEBUG)

application = Flask(__name__)
application.config['SECRET_KEY'] = 'secret-key\'

def get_last_id_updated():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT id FROM last_id_updated ORDER BY id DESC LIMIT 1"
        cursor.execute(sql)
        result = cursor.fetchone()
        return result['id'] if result else None

def update_scores(article_id, russia_score, ukraine_score):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = "UPDATE articles SET Russia_score = %s, Ukraine_score = %s WHERE id = %s"
            cursor.execute(sql, (russia_score, ukraine_score, article_id))
            connection.commit()
    finally:
        connection.close()


def get_article(article_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT * FROM articles WHERE id=%s and category = 'news'"
        cursor.execute(sql, (article_id,))
        article = cursor.fetchone()

    if article is None:
        return None

    if not article['content'] or article['content'] == 'None':
        flash("Pulling the article: ", article_id)
        try:
            # Here you use NewsPlease to get the content
            news_article = NewsPlease.from_url(article['link'])
        except Exception as e:
            flash(f'Error fetching article content: {str(e)}')
            return article
        with connection.cursor() as cursor:
            # You can update the content in your DB here
            sql = "UPDATE articles SET content=%s WHERE id=%s"
            cursor.execute(sql, (news_article.maintext, article_id))
            connection.commit()
            # Update the article's content in the dictionary as well
            article['content'] = news_article.maintext

    return article




def get_db_connection():
    return pymysql.connect(host='russia-ukraine-war-database.cnrtnhsxsjpu.us-east-2.rds.amazonaws.com',
                           user='admin',
                           password='Daniel13776067838.',
                           db='russia-ukraine-war-database',
                           charset='utf8mb4',
                           cursorclass=pymysql.cursors.DictCursor)


@application.route('/test_db_connection')
def test_db_connection():
    try:
        connection = get_db_connection()
        if connection.open:
            connection.close()
            return "Connection successful"
        else:
            return "Connection failed"
    except Exception as e:
        return str(e)


@application.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('user_name')  # changed to match HTML form
        password = request.form.get('password')
        print(username,password)

        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "SELECT * FROM `users` WHERE `user_name`=%s"
            cursor.execute(sql, (username,))
            user = cursor.fetchone()

        if user:
            if user['password'] == password:
                session['user'] = user['user_name']
                return redirect(url_for('home'))
            else:
                flash('Incorrect password. Please try again.')
        else:
            flash('Username does not exist. Please try again.')
    return render_template('login.html')



@application.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.pop('user', None)
    # Clear all session data
    session.clear()
    return redirect(url_for('login'))


@application.route('/', methods=['GET', 'POST'])
def home():
    if 'user' not in session:
        return redirect(url_for('login'))

    if 'current_article_id' not in session:
        last_id_updated = get_last_id_updated()
        session['current_article_id'] = last_id_updated if last_id_updated else 1

    connection = get_db_connection()
    with connection.cursor() as cursor:

        sql = "SELECT * FROM `articles` WHERE `category` = 'news' and `id`=%s"
        cursor.execute(sql, (session['current_article_id'],))
        current_article = cursor.fetchone()

        current_article = get_article(current_article['id'])

        sql = "SELECT * FROM `articles` WHERE `category` = 'news' and `id` <= %s ORDER BY `id` DESC LIMIT 6"
        cursor.execute(sql, (session['current_article_id'],))
        articles_before = cursor.fetchall()

        sql = "SELECT * FROM `articles` WHERE `category` = 'news' and `id` > %s ORDER BY `id` ASC LIMIT 5"
        cursor.execute(sql, (session['current_article_id'],))
        articles_after = cursor.fetchall()

    # Get and potentially update the content for all articles
    articles_before = [get_article(article['id']) for article in articles_before if article is not None]
    articles_after = [get_article(article['id']) for article in articles_after if article is not None]

    articles = list(reversed(articles_before)) + articles_after

    if current_article:
        return render_template('home.html', current_article=current_article, article_id=current_article['id'],
                           articles=articles)
    else:
        return render_template('home.html',
                               message="No current article found")  # Change this to whatever error handling you prefer





@application.route('/next_article', methods=['POST'])
def next_article():
    if 'user' not in session:
        return redirect(url_for('login'))
    print("hi")
    if 'current_article_id' in session:
        print('hello')
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM articles WHERE category='news' AND id > %s ORDER BY id ASC LIMIT 1", (session['current_article_id'],))
            result = cursor.fetchone()
            print('result: ', result)
        if result is not None:
            session['current_article_id'] = result['id']
            session.modified = True
    return redirect(url_for('home'))

@application.route('/previous_article', methods=['POST'])
def previous_article():
    if 'user' not in session:
        return redirect(url_for('login'))
    if 'current_article_id' in session:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM articles WHERE category='news' AND id < %s ORDER BY id DESC LIMIT 1", (session['current_article_id'],))
            result = cursor.fetchone()
            print('result: ', result)
        if result is not None:
            session['current_article_id'] = result['id']
            session.modified = True
    return redirect(url_for('home'))



@application.route('/update_score', methods=['POST'])
def update_score():
    if 'user' not in session:
        return redirect(url_for('login'))

    article_id = request.form.get('article_id')  # Get 'article_id' from form
    print('article_id: ', article_id)
    if article_id is None:
        flash('No article ID provided.', 'danger')
        return redirect(url_for('home'))

    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT Russia_score, Ukraine_score FROM articles WHERE id=%s"
        cursor.execute(sql, (article_id,))
        article = cursor.fetchone()

    if article is None:
        flash('Article not found.', 'danger')
        return redirect(url_for('home'))

    if article['Russia_score'] or article['Ukraine_score']:
        flash('Score has already been updated for this article.', 'warning')
        return redirect(url_for('home'))

    try:
        russia_score = int(request.form.get('russia_score'))  # or float, if scores can be fractional
        ukraine_score = int(request.form.get('ukraine_score'))  # or float, if scores can be fractional
    except (TypeError, ValueError):
        flash('Invalid scores provided.', 'danger')
        return redirect(url_for('home'))

    update_scores(article_id, russia_score, ukraine_score)

    flash('Score updated successfully.', 'success')
    return redirect(url_for('home'))


if __name__ == '__main__':
    application.run(debug=True)

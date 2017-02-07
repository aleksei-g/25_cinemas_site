import re
import os
from datetime import datetime
from multiprocessing import Pool
import requests
from flask import Flask, render_template, request, make_response, redirect, \
    jsonify, send_from_directory
from werkzeug.contrib.cache import SimpleCache
from afisha import parse_afisha_films_list, parse_afisha_cities, \
    parse_afisha_film_detail, get_url_afisha_for_city


HEROKU_LIMIT = 50
CACHE_TIMEOUT = 60 * 60 * 12
COOKIE_AGE = 604800
POOL_COUNT = 4
DEFAULT_CITY_ID = 'msk'
DEFAULT_CITY_NAME = 'Москва'
app = Flask(__name__)
cache = SimpleCache()


def get_page(url):
    return requests.get(url).text


def get_films_list(city=DEFAULT_CITY_ID):
    films = cache.get('films') or []
    if not films or city not in films[0].get('cinemas_count', {}).keys():
        url_afisha = get_url_afisha_for_city(city)
        afisha_page = get_page(url_afisha)
        new_films = parse_afisha_films_list(afisha_page, city)
        if films:
            new_film_without_detail_info = []
            for new_film in new_films:
                film = next((item for item in films if item['film'] ==
                             new_film['film']), None)
                if film:
                    film['cinemas_count'].update(new_film['cinemas_count'])
                else:
                    new_film_without_detail_info.append(new_film)
        else:
            new_film_without_detail_info = new_films
        pool = Pool(POOL_COUNT)
        new_films = pool.map(get_film_detail,
                             new_film_without_detail_info[:HEROKU_LIMIT])
        pool.close()
        pool.join()
        films = films + new_films
        cache.set('films', films, timeout=CACHE_TIMEOUT)
    return films


def get_film_detail(film):
    film_page = get_page(film['url'])
    film_detail = parse_afisha_film_detail(film_page)
    img_small = re.sub(r'^.*.net/',
                       r'https://img06.rl0.ru/afisha/355x200/s1.afisha.net/',
                       film_detail.get('image', ''))
    img_medium = re.sub(r'^.*\.net/',
                        r'https://img06.rl0.ru/afisha/623x350/s1.afisha.net/',
                        film_detail.get('image', ''))
    film_id = re.findall(r'(?<=/)\d+(?=/)', film.get('url'))
    film_id = int(film_id[0]) if film_id else None
    date_published = film_detail.get('datePublished', None)
    year = datetime.strptime(date_published, "%Y-%m-%dT%H:%M:%S").year \
        if date_published else None
    duration = film_detail.get('duration', {'name': 'PT0H0M'})['name']
    duration = int(re.sub(r'PT(\d+)H(\d+)M', lambda m:
                          str(int(m.group(1)) * 60 + int(m.group(2))),
                          duration))
    film.update({'film_id': film_id,
                 'img_small': img_small,
                 'img_medium': img_medium,
                 'year': year,
                 'duration': duration,
                 'actor': film_detail.get('actor', [{'name': '', 'url': ''}]),
                 'aggregateRating': film_detail.get('aggregateRating',
                                                    {'bestRating': 0,
                                                     'ratingCount': 0,
                                                     'ratingValue': 0}),
                 'description': film_detail.get('description', ''),
                 'director': film_detail.get('director', {'name': '',
                                                          'url': ''}),
                 'genre': film_detail.get('genre', ''),
                 'image': film_detail.get('image', ''),
                 'text': film_detail.get('text', ''),
                 'alternativeHeadline': film_detail.get('alternativeHeadline',
                                                        '')
                 })
    return film


def apply_filters_to_films_list(films, city, top_size=10, cinemas_over=1,
                                rating_over=0):
    films.sort(key=lambda d: float(d.get('aggregateRating',
                                         {'ratingValue': 0})['ratingValue']),
               reverse=True)
    films = list(filter(lambda d: d.get('cinemas_count', {}).get(city, 0) >=
                        cinemas_over,
                        films))
    films = list(filter(lambda d: float(d.get('aggregateRating',
                                        {'ratingValue': 0})['ratingValue']) >=
                        rating_over,
                        films))
    return films[:top_size]


def get_cities_list():
    cities = cache.get('cities')
    if cities is None:
        url_afisha = get_url_afisha_for_city()
        afisha_page = get_page(url_afisha)
        cities = parse_afisha_cities(afisha_page)
        cache.set('cities', cities, timeout=CACHE_TIMEOUT)
    return cities


def cities_divided_by_columns(cities, column=6):
    cities = sorted(cities.items(), key=lambda city: city[1])
    len_one_colunm = len(cities) // column + 1
    cities_list_divided = [cities[i:i+len_one_colunm]
                           for i in range(0, len(cities), len_one_colunm)]
    return cities_list_divided


def get_city_from_cookie(request, cities, default_city):
    city = request.cookies.get('city')
    if city not in cities.keys():
        city = default_city
    return city


@app.route('/')
def films_list():
    cities = get_cities_list()
    top_size = request.args.get('top_size', 10, type=int)
    cinemas_over = request.args.get('cinemas_over', 1, type=int)
    rating_over = request.args.get('rating_over', 0, type=float)
    city = get_city_from_cookie(request, cities, DEFAULT_CITY_ID)
    selected_city_name = cities.get(city, DEFAULT_CITY_NAME)
    films = get_films_list(city)
    films = apply_filters_to_films_list(films=films,
                                        top_size=top_size,
                                        cinemas_over=cinemas_over,
                                        rating_over=rating_over,
                                        city=city)
    resp = \
        make_response(render_template('films_list.html',
                                      films=films,
                                      cities=cities_divided_by_columns(cities),
                                      top_size=top_size,
                                      cinemas_over=cinemas_over,
                                      rating_over=rating_over,
                                      selected_city_name=selected_city_name,
                                      city=city,
                                      header='Главная'
                                      ))
    resp.set_cookie('city', city, max_age=COOKIE_AGE)
    return resp


@app.route('/<city>/')
def city_set(city):
    resp = redirect(request.referrer)
    resp.set_cookie('city', city, max_age=COOKIE_AGE)
    return resp


@app.route('/movie/<int:film_id>/')
def film_detail(film_id):
    cities = get_cities_list()
    city = get_city_from_cookie(request, cities, DEFAULT_CITY_ID)
    selected_city_name = cities.get(city, DEFAULT_CITY_NAME)
    films = get_films_list(city)
    film = next((item for item in films if item['film_id'] == film_id), None)
    return render_template('film_detail.html',
                           film=film,
                           city=city,
                           cities=cities_divided_by_columns(cities),
                           selected_city_name=selected_city_name,
                           header=film['film'])


@app.route('/api')
def api_about():
    cities = get_cities_list()
    city = get_city_from_cookie(request, cities, DEFAULT_CITY_ID)
    selected_city_name = cities.get(city, DEFAULT_CITY_NAME)
    return render_template('about_api.html',
                           city=city,
                           cities=cities_divided_by_columns(cities),
                           selected_city_name=selected_city_name,
                           header='API'
                           )


@app.route('/api/get_films_list')
def api_films_list():
    top_size = request.args.get('top_size', -1, type=int)
    cinemas_over = request.args.get('cinemas_over', 1, type=int)
    rating_over = request.args.get('rating_over', 0, type=float)
    city = request.args.get('city', DEFAULT_CITY_ID, type=str)
    films = get_films_list(city)
    films = apply_filters_to_films_list(films=films,
                                        top_size=top_size,
                                        cinemas_over=cinemas_over,
                                        rating_over=rating_over,
                                        city=city)
    return jsonify(results=films)


@app.route('/api/movie/<int:film_id>')
def api_film_detail(film_id):
    city = request.args.get('city', DEFAULT_CITY_ID, type=str)
    films = get_films_list(city)
    film = next((item for item in films if item['film_id'] == film_id), None)
    return jsonify(results=film)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/img'),
                               'favicon.ico',
                               mimetype='image/vnd.microsoft.icon')


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=False)

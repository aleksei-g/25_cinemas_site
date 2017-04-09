from multiprocessing import Pool
import requests
from flask import Flask, render_template, request, make_response, redirect, \
    jsonify
from werkzeug.contrib.cache import SimpleCache
from afisha import parse_afisha_films_list, parse_afisha_cities, \
    parse_afisha_film_detail, get_url_afisha_for_city


HEROKU_LIMIT = 30
CACHE_TIMEOUT = 60 * 60 * 12
COOKIE_AGE = 604800
POOL_COUNT = 4
DEFAULT_CITY_ID = 'msk'
DEFAULT_CITY_NAME = 'Москва'
app = Flask(__name__)
cache = SimpleCache()


def fetch_page(url):
    return requests.get(url).text


def get_films_for_city(city):
    url_afisha = get_url_afisha_for_city(city)
    afisha_page = fetch_page(url_afisha)
    return parse_afisha_films_list(afisha_page, city)


def split_films_into_load_and_not_load(films_in_memory, checking_films):
    if not films_in_memory:
        return [], checking_films
    loaded_films = []
    new_films_without_detail_info = []
    for checking_film in checking_films:
        film = next((item for item in films_in_memory if item['film'] ==
                     checking_film['film']), None)
        if film:
            loaded_films.append(checking_film)
        else:
            new_films_without_detail_info.append(checking_film)
    return loaded_films, new_films_without_detail_info


def get_films_list(city=DEFAULT_CITY_ID):
    films = cache.get('films') or []
    load_cities = cache.get('load_cities') or set()
    if city not in load_cities:
        films_for_city = get_films_for_city(city)
        loaded_films, new_films_without_detail_info = \
            split_films_into_load_and_not_load(films, films_for_city)
        for loaded_film in loaded_films:
            film = next((item for item in films if item['film'] ==
                         loaded_film['film']), None)
            film['cinemas_count'].update(loaded_film['cinemas_count'])
        pool = Pool(POOL_COUNT)
        films_for_city = pool.map(get_film_detail,
                                  new_films_without_detail_info[:HEROKU_LIMIT])
        pool.close()
        pool.join()
        films = [*films, *films_for_city]
        cache.set('films', films, timeout=CACHE_TIMEOUT)
        cache.set('load_cities', load_cities.union({city}),
                  timeout=CACHE_TIMEOUT)
    return films


def get_film_detail(film):
    film_page = fetch_page(film['url'])
    film_detail = parse_afisha_film_detail(film_page)
    return {**film,
            **{'film_id': film_detail.get('film_id'),
               'img_small': film_detail.get('img_small'),
               'img_medium': film_detail.get('img_medium'),
               'year': film_detail.get('year'),
               'duration': film_detail.get('duration'),
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
               }
            }


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
        afisha_page = fetch_page(url_afisha)
        cities = parse_afisha_cities(afisha_page)
        cache.set('cities', cities, timeout=CACHE_TIMEOUT)
    return cities


def cities_divided_by_columns(cities, column=6):
    cities = sorted(cities.items(), key=lambda city: city[1])
    len_one_colunm = len(cities) // column + 1
    cities_list_divided = [cities[i:i+len_one_colunm]
                           for i in range(0, len(cities), len_one_colunm)]
    return cities_list_divided


def get_city_from_cookie(cities, default_city):
    city = request.cookies.get('city')
    if city not in cities:
        city = default_city
    return city


def get_common_context():
    cities = get_cities_list()
    city = get_city_from_cookie(cities, DEFAULT_CITY_ID)
    selected_city_name = cities.get(city, DEFAULT_CITY_NAME)
    return {'cities': cities_divided_by_columns(cities),
            'city': city,
            'selected_city_name': selected_city_name}


@app.route('/')
def films_list():
    common_context = get_common_context()
    top_size = request.args.get('top_size', 10, type=int)
    cinemas_over = request.args.get('cinemas_over', 1, type=int)
    rating_over = request.args.get('rating_over', 0, type=float)
    films = get_films_list(common_context.get('city'))
    films = apply_filters_to_films_list(films=films,
                                        top_size=top_size,
                                        cinemas_over=cinemas_over,
                                        rating_over=rating_over,
                                        city=common_context.get('city'))
    resp = \
        make_response(render_template('films_list.html',
                                      films=films,
                                      top_size=top_size,
                                      cinemas_over=cinemas_over,
                                      rating_over=rating_over,
                                      header='Главная',
                                      common_context=common_context
                                      ))
    resp.set_cookie('city', common_context.get('city'), max_age=COOKIE_AGE)
    return resp


@app.route('/<city>/')
def city_set(city):
    resp = redirect(request.referrer)
    resp.set_cookie('city', city, max_age=COOKIE_AGE)
    return resp


@app.route('/movie/<int:film_id>/')
def film_detail(film_id):
    common_context = get_common_context()
    films = get_films_list(common_context.get('city'))
    film = next((item for item in films if item['film_id'] == film_id), None)
    return render_template('film_detail.html',
                           film=film,
                           common_context=common_context,
                           header=film['film'])


@app.route('/api')
def api_about():
    common_context = get_common_context()
    return render_template('about_api.html',
                           common_context=common_context,
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


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=False)

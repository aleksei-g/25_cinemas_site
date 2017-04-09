import json
import re
from bs4 import BeautifulSoup
from datetime import datetime


def parse_afisha_films_list(page, city):
    soup = BeautifulSoup(page, 'lxml')
    films_list = []
    films_and_cinemas = \
        soup.findAll(
            'div',
            {'class': 'object s-votes-hover-area collapsed'}
        )
    for film_and_cinemas in films_and_cinemas:
        film = film_and_cinemas.find('h3', {'class': 'usetags'}).text
        url = film_and_cinemas.find('h3', {'class': 'usetags'}).\
            find('a').get('href')
        cinemas_count = \
            len(film_and_cinemas.findAll('td', {'class': 'b-td-item'}))
        films_list.append({'film': film,
                           'cinemas_count': {city: cinemas_count},
                           'url': url,
                           })
    return films_list


def parse_afisha_cities(page):
    soup = BeautifulSoup(page, 'lxml')
    cities = {}
    for class_name in ('js-geographyplaceid dd-link bold',
                       'js-geographyplaceid dd-link '):
        cities_raw = soup.findAll('span', {'class': class_name})
        for city_raw in cities_raw:
            city_name = city_raw.text
            city_id = re.findall(r'(?<=/)\w+(?=/$)', city_raw.get('data-href'))
            city_id = city_id[0] if city_id else None
            if city_name and city_id:
                cities[city_id] = city_name
    return cities


def parse_afisha_film_detail(page):
    soup = BeautifulSoup(page, 'lxml')
    film_detail = json.loads(soup.find('script',
                                       {'type': 'application/ld+json'}).text)
    film_detail['img_small'] = \
        re.sub(r'^.*.net/',
               r'https://img06.rl0.ru/afisha/355x200/s1.afisha.net/',
               film_detail.get('image', ''))
    film_detail['img_medium'] = \
        re.sub(r'^.*\.net/',
               r'https://img06.rl0.ru/afisha/623x350/s1.afisha.net/',
               film_detail.get('image', ''))
    film_id = re.findall(r'(?<=/)\d+(?=/)', page)
    film_detail['film_id'] = int(film_id[0]) if film_id else None
    film_detail['date_published'] = film_detail.get('datePublished', None)
    film_detail['year'] = \
        datetime.strptime(film_detail['date_published'],
                          "%Y-%m-%dT%H:%M:%S").year \
        if film_detail.get('datePublished', None) else None
    duration = film_detail.get('duration', {'name': 'PT0H0M'})['name']
    film_detail['duration'] = \
        int(re.sub(r'PT(\d+)H(\d+)M', lambda m:
                   str(int(m.group(1)) * 60 + int(m.group(2))),
                   duration))
    return film_detail


def get_url_afisha_for_city(city='msk'):
    return 'http://www.afisha.ru/{}/schedule_cinema/'.format(city)

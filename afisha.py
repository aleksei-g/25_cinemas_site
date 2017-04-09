import json
import re
from bs4 import BeautifulSoup


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
    return json.loads(soup.find('script',
                                {'type': 'application/ld+json'}).text)


def get_url_afisha_for_city(city='msk'):
    return 'http://www.afisha.ru/{}/schedule_cinema/'.format(city)

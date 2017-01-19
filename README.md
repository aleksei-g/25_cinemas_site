# Cinemas Site

# Что в кино

Сайт [Что в кино](https://top-films.herokuapp.com/) выводит список самых популярных фильмов идущих в кинотеатрах вашего города.

Список фильмов можно отфильтровать по рейтингу и количеству кинотеатров, а так же указать размер топ-листа.

**Важно**

Все данные о фильмах взяты с сайта [Афишы](https://www.afisha.ru/).

Для корректоной работы необходимо установить следующие модули:
* **requests**
* **beautifulsoup4**
* **lxml**
* **flask**
* **gunicorn**

Пакеты устанавливаются командой `pip install -r requirements.txt`.

Для запуска приложения необходимо выполнить команду:
```
gunicorn server:app
```
Приложение будет находиться по адресу 
[http://127.0.0.1:8000](http://127.0.0.1:8000).


# Project Goals

The code is written for educational purposes. Training course for web-developers - [DEVMAN.org](https://devman.org)

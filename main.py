import sys
import time
from datetime import datetime

import requests

# Сервисный ключ приложения VK (users.get, friends.get, wall.get, groups.*)
SERVICE_TOKEN = 'ваш токен'
# Пользовательский токен (нужен для photos.get и users.getSubscriptions)
USER_TOKEN = 'ваш токен'

API_URL = 'https://api.vk.com/method/'
API_VERSION = '5.131'
# Пауза между запросами, чтобы не упереться в лимит VK API (3 запроса/сек)
REQUEST_DELAY = 0.4

INTEREST_FIELDS = {
    'activities': 'Деятельность',
    'interests': 'Интересы',
    'music': 'Любимая музыка',
    'movies': 'Любимые фильмы',
    'tv': 'Любимые телешоу',
    'books': 'Любимые книги',
    'games': 'Любимые игры',
    'about': 'О себе',
}


def vk_request(method, access_token, **params):
    """Вызывает метод VK API и возвращает поле 'response' или None при ошибке."""
    time.sleep(REQUEST_DELAY)
    params.update(access_token=access_token, v=API_VERSION)
    try:
        data = requests.get(API_URL + method, params=params, timeout=10).json()
    except (requests.RequestException, ValueError) as error:
        print(f'Ошибка запроса {method}: {error}')
        return None

    if 'error' in data:
        print(f"Ошибка VK API ({method}): {data['error'].get('error_msg')}")
        return None
    return data.get('response')


def get_user(user_id, access_token, fields=''):
    users = vk_request('users.get', access_token, user_ids=user_id, fields=fields)
    return users[0] if users else None


def get_vk_id(username, access_token):
    user = get_user(username, access_token)
    if user is None:
        print('Пользователь не найден.')
        return None
    return user['id']


def get_wall_photos(vk_id, access_token, count=15):
    """Возвращает список фото со стены: id, ссылка на оригинал, подпись, лайки."""
    response = vk_request('photos.get', access_token, owner_id=vk_id, album_id='wall',
                          extended=1, count=count)
    if response is None:
        return []
    return [{
        'id': photo['id'],
        'url': photo.get('orig_photo', {}).get('url', ''),
        'text': photo.get('text', ''),
        'likes': photo['likes']['count'],
    } for photo in response['items']]


# Подписки пользователя (на людей и сообщества)

def get_user_subscriptions(vk_id, access_token):
    response = vk_request('users.getSubscriptions', access_token, user_id=vk_id,
                          extended=1, count=200)
    return response['items'] if response else []


def get_group_info(group_id, access_token):
    groups = vk_request('groups.getById', access_token, group_id=group_id, fields='description')
    if not groups:
        return None
    group = groups[0]
    return {
        'id': group_id,
        'name': group.get('name', 'Название не найдено'),
        'description': group.get('description', 'Описание не найдено'),
    }


def get_subscriptions_info(vk_id, access_token):
    subscriptions_info = []
    for subscription in get_user_subscriptions(vk_id, access_token):
        if subscription['type'] == 'profile':
            user = get_user(subscription['id'], access_token, fields='domain')
            if user:
                subscriptions_info.append({
                    'id': user['id'],
                    'name': f"{user['first_name']} {user['last_name']}",
                    'description': user.get('domain', 'Домен не найден'),
                })
        elif subscription['type'] == 'page':
            group = get_group_info(subscription['id'], access_token)
            if group:
                subscriptions_info.append(group)
    return subscriptions_info


# Друзья

def get_friends_count(vk_id, access_token):
    response = vk_request('friends.get', access_token, user_id=vk_id, count=1)
    return response['count'] if response else None


def get_friends_info(vk_id, access_token):
    """Город, вуз и место работы каждого друга."""
    response = vk_request('friends.get', access_token, user_id=vk_id,
                          fields='city,education,occupation')
    if response is None:
        return []
    return [{
        'id': friend['id'],
        'city': friend.get('city', {}).get('title', 'Не указан'),
        'education': friend.get('university_name') or 'Не указано',
        'job': friend.get('occupation', {}).get('name', 'Не указано'),
    } for friend in response['items']]


# Возраст

def get_birth_date(vk_id, access_token):
    user = get_user(vk_id, access_token, fields='bdate')
    return user.get('bdate') if user else None


def get_age(birth_date):
    """Возраст по дате вида 'Д.М.ГГГГ'. Если год скрыт ('Д.М'), возвращает None."""
    try:
        born = datetime.strptime(birth_date, '%d.%m.%Y')
    except ValueError:
        return None
    today = datetime.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


# Статистика страницы

def get_average_likes(items):
    return sum(item['likes']['count'] for item in items) / len(items) if items else 0


def get_average_post_likes(vk_id, access_token):
    response = vk_request('wall.get', access_token, owner_id=vk_id, count=100, extended=1)
    return get_average_likes(response['items']) if response else None


def get_average_photo_likes(vk_id, access_token):
    response = vk_request('photos.get', access_token, owner_id=vk_id, album_id='profile',
                          extended=1)
    return get_average_likes(response['items']) if response else None


def get_posts_count(vk_id, access_token):
    response = vk_request('wall.get', access_token, owner_id=vk_id, count=1)
    return response['count'] if response else None


def get_photos_count(vk_id, access_token):
    response = vk_request('photos.get', access_token, owner_id=vk_id, album_id='profile', count=1)
    return response['count'] if response else None


def get_interests(vk_id, access_token):
    user = get_user(vk_id, access_token, fields=','.join(INTEREST_FIELDS))
    if user is None:
        return None
    return '; '.join(f'{title}: {user[field]}'
                     for field, title in INTEREST_FIELDS.items() if user.get(field))


def print_if_found(title, value):
    if value is not None:
        print(f'{title}: {value}')


def main():
    username = sys.argv[1] if len(sys.argv) > 1 else input('Введите id или короткое имя пользователя VK: ')

    vk_id = get_vk_id(username, SERVICE_TOKEN)
    if vk_id is None:
        return

    print_if_found(f'Количество друзей у {username}', get_friends_count(vk_id, SERVICE_TOKEN))

    birth_date = get_birth_date(vk_id, SERVICE_TOKEN)
    print_if_found('Дата рождения', birth_date)
    if birth_date:
        print_if_found('Возраст', get_age(birth_date))

    print_if_found('Количество постов', get_posts_count(vk_id, SERVICE_TOKEN))
    post_likes = get_average_post_likes(vk_id, SERVICE_TOKEN)
    print_if_found('Среднее количество лайков на постах', post_likes and round(post_likes))

    print_if_found('Количество фото профиля', get_photos_count(vk_id, USER_TOKEN))
    photo_likes = get_average_photo_likes(vk_id, USER_TOKEN)
    print_if_found('Среднее количество лайков на фото', photo_likes and round(photo_likes))

    print_if_found('Интересы', get_interests(vk_id, SERVICE_TOKEN) or None)

    print('\nФото со стены:')
    for photo in get_wall_photos(vk_id, USER_TOKEN):
        print(f"{photo['id']} | {photo['url']} | {photo['text']} | лайков: {photo['likes']}")

    print('\nПодписки:')
    for subscription in get_subscriptions_info(vk_id, USER_TOKEN):
        print(f"ID: {subscription['id']}")
        print(f"Название/Имя: {subscription['name']}")
        print(f"Описание/Домен: {subscription['description']}")
        print('-' * 40)

    print('\nДрузья:')
    for friend in get_friends_info(vk_id, SERVICE_TOKEN):
        print(f"ID: {friend['id']}")
        print(f"Город: {friend['city']}")
        print(f"Образование: {friend['education']}")
        print(f"Работа: {friend['job']}")
        print('-' * 40)


if __name__ == '__main__':
    main()

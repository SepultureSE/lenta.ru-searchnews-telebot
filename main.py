from fake_useragent import UserAgent
from configparser import ConfigParser
from bs4 import BeautifulSoup
from keyboa import keyboa_maker
from datetime import datetime
import sqlite3
import lxml
import requests
import telebot
import os


class Config:
    """ Класс для взаимодействия с конфигурационным файлом """
    default_config_name = 'config.ini'  # название конфигурационного файла по-умолчанию

    def __init__(self):
        self.__config = ConfigParser()

        # создает новый конфиг. файл, если указанный не был найден
        if not os.path.exists(self.default_config_name):
            self.create_config_file()

        # парсит конфиг. файл и присваивает эти данные атрибутам экземпляра
        self.__config.read(self.default_config_name)
        self.token = self.__config.get('BOT_SETTINGS', 'token')
        self.search_responses_limit = self.__config.get('PARSER_SETTINGS', 'search_responses_limit')
        self.main_news_limit = self.__config.get('PARSER_SETTINGS', 'main_news_limit')

    def create_config_file(self):
        """ Метод, создающий новый конфиг. файл """
        # заполняет секцию с настройками бота
        self.__config.add_section('BOT_SETTINGS')
        self.__config.set('BOT_SETTINGS', 'token', 'None')

        # создает секцию с настройками парсера
        self.__config.add_section('PARSER_SETTINGS')
        self.__config.set('PARSER_SETTINGS', 'search_responses_limit', '5')
        self.__config.set('PARSER_SETTINGS', 'main_news_limit', '5')

        # создает конфиг. файл и заполняет его секциями
        with open(self.default_config_name, 'w') as config_file:
            self.__config.write(config_file)


class Database:
    """ Класс для управления БД """
    def __init__(self):
        self.__connection = sqlite3.connect('data.sqlite', check_same_thread=False)
        self.__cursor = self.__connection.cursor()
        self.__create_database()

    def __create_database(self):
        """ Создает базу данных """
        self.__cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER,
            username TEXT,
            start_time TEXT
        );''')
        self.__connection.commit()

        self.__cursor.execute('''CREATE TABLE IF NOT EXISTS requests (
            telegram_id INTEGER,
            start_time TEXT,
            request_type TEXT,
            request_data TEXT
        );''')
        self.__connection.commit()

    def add_user(self, telegram_id: int, username: str, start_time: datetime) -> int:
        """ Добавить пользователя в таблицу """
        self.__cursor.execute(f'SELECT telegram_id FROM users WHERE telegram_id={telegram_id};')

        if self.__cursor.fetchone() is None:
            self.__cursor.execute('INSERT INTO users VALUES (?, ?, ?);', (telegram_id, username, start_time))
            self.__connection.commit()
            return 1
        else:
            return 0

    def get_all_users(self) -> list:
        """ Возвращает двумерный массив с данными всех пользователей """
        self.__cursor.execute('SELECT * FROM users;')
        return self.__cursor.fetchall()

    def get_specific_user(self, telegram_id: int) -> tuple:
        """ Возвращает одномерный массив с данными пользователя """
        self.__cursor.execute(f'SELECT * FROM users WHERE telegram_id={telegram_id};')
        return self.__cursor.fetchone()

    def update_username(self, telegram_id: int, username: str) -> None:
        """ Изменяет юзернейм пользователя на более новый """
        self.__cursor.execute(f'UPDATE users SET username="{username}" WHERE telegram_id={telegram_id};')
        self.__connection.commit()

    def add_request(self, telegram_id: int, start_time: datetime, request_type: str, request_data: str) -> None:
        """ Добавляет запись с новым запросом """
        self.__cursor.execute(f'INSERT INTO requests VALUES (?, ?, ?, ?);',
                              (telegram_id, start_time, request_type, request_data))
        self.__connection.commit()

    def get_all_requests(self) -> list:
        """ Возващает двумерный массив со всеми запросами """
        self.__cursor.execute(f'SELECT * FROM requests;')
        return self.__cursor.fetchall()

    def get_main_requests(self) -> list:
        """ Возвращает двумерный массив главных запросов """
        self.__cursor.execute(f'SELECT * FROM requests WHERE request_type="main_news";')
        return self.__cursor.fetchall()

    def get_searched_requests(self) -> list:
        """ Возвращает двумерный массив запросов по поиску """
        self.__cursor.execute(f'SELECT * FROM requests WHERE request_type="news_by_request";')
        return self.__cursor.fetchall()


class Parser:
    """ Класс парсера Lenta.ru """
    @staticmethod
    def get_main_news(max_news: int) -> list:
        """ Возвращает двумерный массив содержащий ссылки и названия главных новостей """
        # отпралвяет GET запрос на сайт и парсит содержимое блока "Главные новости"
        # пришлось прибегнуть к парсингу из-за того, что главные новости не выгружаются
        # запросом, как я понял
        r = requests.get('https://lenta.ru/')
        soup = BeautifulSoup(r.text, features='lxml')
        main_news_block = soup.findChild('div', attrs={'class': 'b-yellow-box__wrap'})
        main_news_div_list = main_news_block.find_all('a')
        main_news_sorted_list = list()

        # отделяет ссылку на статью от заголовка статьи
        for total, post in enumerate(main_news_div_list):
            # если достигнут предел статей, который указан в CONFIG.INI -
            # останавливает цикл
            if total >= int(max_news):
                break

            # добавляет все полученные данные в двумерный массив, удаляет ненужные
            # символы и приводит ссылку в нужный вид
            main_news_sorted_list.append((
                post.text.replace('\xa0', ' '), 'https://lenta.ru' + post['href']
            ))

        return main_news_sorted_list

    @staticmethod
    def get_news_by_request(request: str, max_news: int) -> list:
        # создает заголовок со случайным user-agent`ом
        fake_agent = {'user_agent': UserAgent().random}

        # GET запрос на статьи по поиску с определенным количеством.
        # (Проанализировав этот ресурс я пришел к выводу, что
        # с помощью этого запроса можно получить неограниченное количество статей)
        r = requests.get('https://lenta.ru/search/v2/process', headers=fake_agent, params={
            'from': '0',
            'size': str(max_news),
            'sort': '2',
            'title_only': '1',
            'domain': '1',
            'query': request
        })

        # двумерный массив, состоящий из заголовка статьи и ссылки
        found_articles = list()

        # добавление в двумерный массив кортежи с заголовком и ссылкой статьи
        for post in r.json()['matches']:
            found_articles.append((post['title'], post['rightcol'], post['url']))

        return found_articles


def main():
    """ Функционал Telegram бота """
    global received_data, page

    def found_articles_inline(article_url: str) -> str:
        """ Создает Inline клавиатуру новостей по запросу с указанной для кнопки чтения ссылкой """
        return telebot.types.InlineKeyboardMarkup().row(
            telebot.types.InlineKeyboardButton(text='🔙', callback_data='found_articles_left'),
            telebot.types.InlineKeyboardButton(text='📓 Read', callback_data='found_articles_read', url=article_url),
            telebot.types.InlineKeyboardButton(text='🔜', callback_data='found_articles_right')
        )

    def main_news_inline(article_url: str) -> str:
        """ Создает Inline клавиатуру главных новостей с указанной для кнопки чтения ссылкой """
        return telebot.types.InlineKeyboardMarkup().row(
            telebot.types.InlineKeyboardButton(text='🔙', callback_data='main_news_left'),
            telebot.types.InlineKeyboardButton(text='📓 Read', callback_data='main_news_read', url=article_url),
            telebot.types.InlineKeyboardButton(text='🔜', callback_data='main_news_right')
        )

    # создание клавиатуры навигации по функционалу бота
    menu_keyboard = telebot.types.ReplyKeyboardMarkup(True, False)  # создание ReplyMarkup клавиатуры

    menu_keyboard.row('☑ Главные новости')  # добавление шаблона для поиска главных новостей
    menu_keyboard.row('👁‍🗨 Поиск новостей')  # добавление шаблона для поиска новостей, введенных пользователем

    def create_page_nav(data: list, input_page: int) -> dict:
        """ Возвращает результат постраничной навигации """
        list_to_dict = dict()

        # конвертирование list в dict
        for index, element in enumerate(data):
            list_to_dict[index + 1] = element

        return list_to_dict[input_page]

    @bot.message_handler(commands=['start'])
    def start_message(message):
        """ Вывод стартового сообщения """
        db.add_user(message.from_user.id, message.from_user.username, datetime.now())

        bot.send_message(message.chat.id, '''👁‍🗨 Поиск новостей | *Lenta.ru*\n
Этот бот предназначен для поиска новостей на сайте *Lenta.ru*.
Используйте клавиатуру Telegram\`а для навигации по функционалу бота''',
                         parse_mode='Markdown', reply_markup=menu_keyboard)

    @bot.message_handler(content_types=['text'])
    def parsing_mode(message):
        """ Ответ на выбор функции бота н ReplyMarkup клавиатуре """
        global received_data, page

        db.update_username(message.from_user.id, message.from_user.username)

        if message.text == '☑ Главные новости':
            page = 1
            bot.send_message(message.from_user.id, '📡 *Поиск статей на ресурсе ...*', parse_mode='Markdown')

            received_data = Parser.get_main_news(config.main_news_limit)
            construct_message = f'📮 *{received_data[page - 1][0]}*\n\n\n📃 Страница: {page}/{len(received_data)}'

            bot.send_message(message.from_user.id, construct_message,
                             parse_mode='Markdown', reply_markup=main_news_inline(received_data[page - 1][1]))

        elif message.text == '👁‍🗨 Поиск новостей':
            page = 1
            msg = bot.send_message(message.from_user.id, '🎙 *Введите название статьи*', parse_mode='Markdown')

            # ожидает от пользователя ответ
            bot.register_next_step_handler(msg, searched_news_response)

        else:
            bot.send_message(message.from_user.id, '❌ *Неизвестная команда*', parse_mode='Markdown')

    def searched_news_response(message):
        """ Вызывается после поискового запроса пользователя. Ищет статьи по запросу на ресурсе """
        global received_data

        bot.send_message(message.from_user.id, '📡 *Поиск статей на ресурсе ...*', parse_mode='Markdown')
        received_data = Parser.get_news_by_request(message.text, config.main_news_limit)

        if len(received_data) == 0:
            bot.send_message(message.from_user.id,
                '❌ *Ни одной статьи по вашему поисковому запросу не было найдено*', parse_mode='Markdown')
            return

        data_for_message = create_page_nav(received_data, page)

        construct_message = f'''📮 *{data_for_message[0]}*
\n_— {data_for_message[1]}_\n\n\n📃 Страница: {page}/{len(received_data)}'''

        bot.send_message(message.from_user.id, construct_message, parse_mode='Markdown',
                         disable_web_page_preview=True, reply_markup=found_articles_inline(data_for_message[2]))

    @bot.callback_query_handler(func=lambda call: call.data in ['found_articles_left', 'found_articles_right'])
    def found_articles_page_navigation(call):
        """ Постраничная навигация """
        global page, received_data

        if call.data == 'found_articles_left':
            if page == 1:
                page = len(received_data)
            else:
                page -= 1

        elif call.data == 'found_articles_right':
            if page == len(received_data):
                page = 1
            else:
                page += 1

        try:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text=f'''📮 *{create_page_nav(received_data, page)[0]}*
\n_— {create_page_nav(received_data, page)[1]}_\n\n
📃 Страница: {page}/{len(received_data)}''',
                                  parse_mode='Markdown', reply_markup=found_articles_inline(received_data[page - 1][2]))
        except telebot.apihelper.ApiException:
            pass

        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data in ['main_news_left', 'main_news_right'])
    def main_news_page_navigation(call):
        """ Постраничная навигация """
        global page, received_data

        if call.data == 'main_news_left':
            if page == 1:
                page = len(received_data)
            else:
                page -= 1

        elif call.data == 'main_news_right':
            if page == len(received_data):
                page = 1
            else:
                page += 1

        try:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text=f'''📮 *{create_page_nav(received_data, page)[0]}*
\n\n📃 Страница: {page}/{len(received_data)}''',
                                  parse_mode='Markdown', reply_markup=main_news_inline(received_data[page - 1][1]))
        except telebot.apihelper.ApiException:
            pass

        bot.answer_callback_query(call.id)

    bot.polling(none_stop=True)


if __name__ == '__main__':
    page = 1  # стартовая страница
    received_data = 'None'  # имеющиеся на данный момент данные

    # создает все необходимые экземпляры
    config = Config()
    bot = telebot.TeleBot(config.token)
    db = Database()

    # запускает основной код бота
    main()
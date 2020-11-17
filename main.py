from fake_useragent import UserAgent
from configparser import ConfigParser
from bs4 import BeautifulSoup
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
    def get_news_by_request(request: str, max_news: int):
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
        responses = list()

        # добавление в двумерный массив кортежи с заголовком и ссылкой статьи
        for post in r.json()['matches']:
            responses.append((post['title'], post['url']))

        return responses


def main():
    """ Функционал Telegram бота """
    # создание клавиатуры навигации по функционалу бота
    menu_keyboard = telebot.types.ReplyKeyboardMarkup(True, False)  # создание ReplyMarkup клавиатуры

    menu_keyboard.row('☑ ️Главные новости')  # добавление шаблона для поиска главных новостей
    menu_keyboard.row('👁‍🗨 Поиск новостей')  # добавление шаблона для поиска новостей, введенных пользователем

    @bot.message_handler(commands=['start'])
    def start_message(message):
        """ Вывод стартового сообщения """
        bot.send_message(message.chat.id, '''👁‍🗨 Поиск новостей | *Lenta.ru*\n
Этот бот предназначен для поиска новостей на сайте *Lenta.ru*.
Используйте клавиатуру Telegram\`а для навигации по функционалу бота''', parse_mode='Markdown', reply_markup=menu_keyboard)

    @bot.message_handler(content_types=['text'])
    def main_news_func(message):
        """ Ответ на выбор функции бота н ReplyMarkup клавиатуре """
        if message.text == '☑ ️Главные новости':
            bot.send_message(message.from_user.id, '📡 *Поиск статей на ресурсе ...*', parse_mode='Markdown')

            construct_message = f'📮 Главные новости *Lenta.ru*\n{" " * 6}_(Названия статей кликабельны)_\n\n'
            for index, post in enumerate(Parser.get_main_news(config.main_news_limit)):
                construct_message += f'{index + 1}) [{post[0]}]({post[1]})\n\n'

            bot.send_message(message.from_user.id, construct_message,
                             parse_mode='Markdown', disable_web_page_preview=True)

        elif message.text == '👁‍🗨 Поиск новостей':
            msg = bot.send_message(message.from_user.id, '🎙 *Введите название статьи*', parse_mode='Markdown')

            # ожидает от пользователя ответ
            bot.register_next_step_handler(msg, searched_news_response)

        else:
            bot.send_message(message.from_user.id, '❌ *Неизвестная команда*', parse_mode='Markdown')

    def searched_news_response(message):
        """ Вызывается после поискового запроса пользователя. Ищет статьи по запросу на ресурсе """
        bot.send_message(message.from_user.id, '📡 *Поиск статей на ресурсе ...*', parse_mode='Markdown')

        construct_message = f'''📮 Найденные статьи на *Lenta.ru*
{" " * 6}_(Названия статей кликабельны)_\n\n'''
        if len(Parser.get_news_by_request(message.text, config.main_news_limit)) != 0:
            for index, post in enumerate(Parser.get_news_by_request(message.text, config.main_news_limit)):
                construct_message += f'{index + 1}) [{post[0]}]({post[1]})\n\n'

            bot.send_message(message.from_user.id, construct_message,
                parse_mode='Markdown', disable_web_page_preview=True)

        else:
            bot.send_message(message.from_user.id, '❌ *Ни одной статьи по вашему поисковому запросу не было найдено*',
                             parse_mode='Markdown')

    bot.polling(none_stop=False)


if __name__ == '__main__':
    # создает все необходимые экземпляры
    config = Config()
    bot = telebot.TeleBot(config.token)

    # запускает основной код бота
    main()
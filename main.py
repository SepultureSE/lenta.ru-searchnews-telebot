import requests
from bs4 import BeautifulSoup
import lxml
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import telebot

TELEGRAM_TOKEN = '1361796344:AAHBoNxIgRYHPJbScXCXa4umhP-jFDkffQI'

bot = telebot.TeleBot(TELEGRAM_TOKEN)  # создание экземпляра класса telebot

# настройка Chrome для безголового режима
headless_options = Options()
headless_options.add_argument('--headless')

# создание Chrome драйвера в безголовом режиме
driver = webdriver.Chrome(options=headless_options, executable_path='chromedriver.exe')

# создание клавиатуры навигации по функционалу бота
menu_keyboard = telebot.types.ReplyKeyboardMarkup(True, False)  # создание ReplyMarkup клавиатуры

menu_keyboard.row('☑️Главные новости')  # добавление шаблона для поиска главных новостей
menu_keyboard.row('👁‍🗨Поиск новостей')  # добавление шаблона для поиска новостей, введенных пользователем


@bot.message_handler(commands=['start', 'help'])
def start_message(message):
    # Вывод стартового сообщения
    bot.send_message(message.chat.id, '''Поиск новостей | *Lenta.ru*
¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯
Это бот для поиска новостей на сайте *Lenta.ru*
Используйте клавиатуру Telegram\`а для навигации по
функционалу бота''', parse_mode='Markdown', reply_markup=menu_keyboard)


@bot.message_handler(content_types=['text'])
def main_news_func(message):
    """ Функционал главных новостей бота """
    if message.text == '☑️Главные новости':
        r = requests.get('https://lenta.ru/')  # получение страницы с главными новостями
        soup = BeautifulSoup(r.text, 'lxml')  # создание экземпляра класса bs4 со страницей Lenta.ru

        # получение родительского элемента <div> с главными новостями
        block = soup.find('div', attrs={'class': 'b-yellow-box__wrap'})

        # получение этих самых новостей
        news = block.findChildren('div', attrs={'class', 'item'}, recursive=False)

        # переменная для составления сообщения с новостями
        message_content = f'''Главные новости дня | *Lenta.ru*
¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯\n'''

        # добавление новостей в итоговое сообщение
        for score, value in enumerate(news):
            title = value.findChild('a').text  # получение заголовка статьи
            link = value.findChild('a').get('href')  # получение ссылки на статью

            message_content += f'{score+1}) {title}\n(*lenta.ru/{link}*)\n\n'  # добавление статьи в итоговое сообщение

        bot.send_message(message.chat.id, message_content, parse_mode='Markdown')  # отправление сообщения

    # функционал поиска новостей по сайту
    elif message.text == '👁‍🗨Поиск новостей':
        msg = bot.send_message(message.chat.id, '''🎙 Введите название статьи и бот найдет несколько похожих новостей''')
        bot.register_next_step_handler(msg, search_news_func)  # ожидание ответа от пользователя


def search_news_func(message):
    bot.send_message(message.chat.id, '*📡 Поиск статей на ресурсе ...*', parse_mode='Markdown')

    # запрос на сайт для составления ссылки
    r = requests.get('https://lenta.ru/search', params={'query': message.text.lower()})

    driver.get(r.url)  # полная загрузка страницы
    source_html = driver.page_source  # получение html-кода страницы
    soup = BeautifulSoup(source_html, 'lxml')  # экземпляр bs4 для парсинга

    # получение <div> блока с найденными статьями
    blocks = soup.findChildren('div', attrs={'class', 'b-search__result-item-title'})

    # переменная для составления итогового сообщения со статьями
    message_content = '''👁‍🗨Результаты поиска
¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯\n'''

    # проверка, если не найдено статей - бот сообщает об этом пользователю
    if len(blocks) == 0:
        bot.send_message(message.chat.id, '*🏴‍☠️ Бот ничего не нашел ...*', parse_mode='Markdown')

    # если же статьи были найдены - он их отображает, но не больше 5
    else:
        for score, value in enumerate(blocks):
            # проверка на количество
            if score + 1 >= 5:
                break

            title = value.findChild('a').text  # получение заголовка статьи
            link = value.findChild('a').get('href')  # получение ссылки на статью

            # добавление статьи в итоговое сообщение
            message_content += f'{score+1}) {title}\n(*lenta.ru/{link}*\n\n'

        # отправка сообщения с найденными статьями
        bot.send_message(message.chat.id, message_content, parse_mode='Markdown')


if __name__ == '__main__':
    bot.polling(none_stop=True)

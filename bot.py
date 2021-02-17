#!/usr/bin/python3

# Created by Mike Kuznetsov <mike4gg@gmail.com>
# Licensed under the terms of GPLv3 https://www.gnu.org/licenses/gpl-3.0.en.html

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
import MySQLdb
import requests
from bs4 import BeautifulSoup
import re

token='XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

myconf = {
    'host': 'localhost',
    'user': 'bus',
    'password': 'XXXXXXXXXXXX',
    'port': 3306,
    'db': 'bus',
}

urls = {
    'station': 'http://online.pskovbus.ru/wap/online/?st_id=',
    'support': 'https://t.me/mikevmk',
}

messages = {
    'help': 'Вся информация берется с официального сайта Псковпассажиравтотранса online.pskovbus.ru, \n\
где она рассчитывается из данных о настоящем местоположении автобуса (GPS-трек) и его примерной скорости, \n\
поэтому полученное время прибытия автобуса может незначительно изменяться с течением времени. \n\
Пишите о найденных в работе бота багах @mikevmk. Оставляйте жалобы на неточное расписание на сайте \n\
online.pskovbus.ru в разделе Ещё -> Написать разработчикам \n\
 \n\
Отправьте /start для начала работы',
    'easter_egg': 'Бип-бип... Убить всех человеков... Должен убить всех человеков...\n...\n...\n\
О, человек! Мне снился прекрасный сон! И ты там был ;-)',
    'choose_route': 'Выберите маршрут 🚍. Для получения справки отправьте /help',
    'choose_direction': 'Выберите направление для маршрута 🚍 № ',
    'choose_station_short': 'Выберите остановку:',
    'choose_station_long': 'Выберите остановку для 🚍 № ',
    'answer_nothing_found': 'Ничего не нашлось. Попробуйте уточнить запрос или используйте команду /start для легкой навигации',
    'answer_toomuch': 'Слишком много результатов. Попробуйте уточнить запрос',
    'answer_server_error': '⚠️ Ошибка: сервер Псковпассажиравтотранса online.pskovbus.ru временно недоступен\n\nПопробуйте посмотреть статические расписания на https://www.pskovbus.ru/?r=2',
    'answer_nothing_returned': 'Псковпассажиравтотранс не вернул данных по этой остановке\n\nПопробуйте посмотреть статические расписания на https://www.pskovbus.ru/?r=2',
    'button_start': '⏪ ',
    'button_support': '🆘 ',
    'button_direction': ' 👉 ' ,
    'button_refresh': '🔄 ',
    'button_coffee': '☕☕',
    'board_prefix': ' 🚌 ',
    'board_middle': '🕒 ',
    'board_disabled': ' ♿',
    'board_header_long': '💉🦠💉 ☎299028 или gosuslugi.ru\n\nРасписание для маршрута 🚍 № ',
    'board_header_short': 'Расписание 🚍',
    'board_header_suffix': ' по остановке ',
    'coffee': 'Угостить меня чашечкой ☕ можно через Сбербанк.Online по 📱 +79517516942\n\nОтправьте /start для начала работы',
}

def mysql_connect():
    myconn = MySQLdb.Connection(
        host=myconf['host'],
        user=myconf['user'],
        passwd=myconf['password'],
        port=myconf['port'],
        db=myconf['db'],
        charset='utf8', 
        use_unicode = True
    )
    cursor = myconn.cursor()
    return myconn, cursor

def mysql_close(myconn, cursor):
    cursor.close()
    myconn.close()

def log_request(message,update):
    try:
	    telegram_username = update.message.from_user.username
	    telegram_firstname = update.message.from_user.first_name
	    telegram_lastname = update.message.from_user.last_name
	    telegram_id = update.message.from_user.id
    except:
	    telegram_username = update.callback_query.from_user.username
	    telegram_firstname = update.callback_query.from_user.first_name
	    telegram_lastname = update.callback_query.from_user.last_name
	    telegram_id = update.callback_query.from_user.id
    logger.info(message + ' %s %s (%s %s)', telegram_id, telegram_username, telegram_firstname, telegram_lastname)

def start_callback(update, context):
    log_request('/start from', update)
    reply_markup = main_menu(routes_active)
    update.message.reply_text(messages['choose_route'], reply_markup=reply_markup)

def help_callback(update, context):
    log_request('/help from', update)
    update.message.reply_text(messages['help'])

def message_callback(update, context):
    try:
        user_message=update.message.text
    except:
        return
    log_request('Update message: ' + user_message, update)
    if user_message in routes_active:
        myconn, cursor = mysql_connect()
        query = 'SELECT route_id FROM routes WHERE route=%s'
        cursor.execute(query, [user_message])
        route_id = cursor.fetchall()[0][0]
        mysql_close(myconn, cursor)
        reply_markup, route = directions_menu(route_id)
        update.message.reply_text(messages['choose_direction'] + route, reply_markup=reply_markup)
    elif ';' in user_message:
        update.message.reply_text(messages['easter_egg'])
    else:
        myconn, cursor = mysql_connect()
        query_search = 'SELECT station_id FROM stations WHERE name_long LIKE %s AND active=1'
        cursor.execute(query_search, ['%' + user_message + '%'])
        station_ids = [item[0] for item in cursor.fetchall()]
        mysql_close(myconn, cursor)
        if len(station_ids) == 0:
            update.message.reply_text(messages['answer_nothing_found'])
        elif len(station_ids) == 1:
            board, route, station = get_board(station_ids[0], "0")
            board = messages['board_header_short'] + messages['board_header_suffix'] + '*' + station + "*\n\n" + board
            markup = []
            markup.append([InlineKeyboardButton(messages['button_start'], callback_data='start'),InlineKeyboardButton(messages['button_refresh'], callback_data='station,' + str(station_ids[0]) + ',0'),InlineKeyboardButton(text=messages['button_support'], callback_data='sos'),InlineKeyboardButton(text=messages['button_coffee'],callback_data='coffee')])
            reply_markup = InlineKeyboardMarkup(markup)
            update.message.reply_text(board, reply_markup=reply_markup, parse_mode='markdown')
        elif len(station_ids) > 20:
            update.message.reply_text(messages['answer_toomuch'])
        else:
            markup = []
            for station_id in station_ids:
                query = 'SELECT name_long FROM stations WHERE station_id=%s'
                myconn, cursor = mysql_connect()
                cursor.execute(query, [str(station_id)])
                station_name_long = cursor.fetchall()[0][0]
                mysql_close(myconn, cursor)
                markup.append([InlineKeyboardButton(station_name_long, callback_data='station,' + str(station_id) + ',0')])
            reply_markup = InlineKeyboardMarkup(markup)
            update.message.reply_text(messages['choose_station_short'], reply_markup=reply_markup)

def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def query_callback(update, context):
    query = update.callback_query
    log_request(query.data, update)
    query_data = query.data.split(",")
    if query_data[0] == 'station':
        station_id = query_data[1]
        route_id = query_data[2]
        board, route, station = get_board(station_id, route_id)
        if not board:
            board = messages['answer_nothing_returned']
        elif route == "0":
            board = messages['board_header_short'] + messages['board_header_suffix'] + "*" + station + "*\n\n" + board
        else:
            board = messages['board_header_long'] + "*" + route + "*" + messages['board_header_suffix'] + "*" + station + "*\n\n" + board
        markup = []
        markup.append([InlineKeyboardButton(messages['button_start'], callback_data='start'),InlineKeyboardButton(messages['button_refresh'], callback_data='station,' + str(station_id) + ',' + route_id),InlineKeyboardButton(text=messages['button_support'], callback_data='sos'),InlineKeyboardButton(text=messages['button_coffee'],callback_data='coffee')])
        reply_markup = InlineKeyboardMarkup(markup)
        context.bot.send_message(query.message.chat_id, board, reply_markup=reply_markup, parse_mode='markdown', disable_web_page_preview=True)
    elif query_data[0] == 'route':
        route_id = query_data[1]
        reply_markup, route = directions_menu(route_id)
        context.bot.send_message(query.message.chat_id, messages['choose_direction'] + route, reply_markup=reply_markup)
    elif query_data[0] == 'direction':
        route_id = query_data[1]
        direction_id = query_data[2]
        reply_markup, route = stations_menu(route_id, direction_id)
        context.bot.send_message(query.message.chat_id, messages['choose_station_long'] + route, reply_markup=reply_markup)
    elif query_data[0] == 'start':
        reply_markup = main_menu(routes_active)
        context.bot.send_message(query.message.chat_id, messages['choose_route'], reply_markup=reply_markup)
    elif query_data[0] == 'coffee':
        context.bot.send_message(query.message.chat_id, messages['coffee'])
    elif query_data[0] == 'sos':
        context.bot.send_message(query.message.chat_id, messages['help'])
    query.answer()

def get_board(station_id, route_id):
    myconn, cursor = mysql_connect()
    if route_id != "0":
        query = 'SELECT route FROM routes WHERE route_id=%s'
        cursor.execute(query, [route_id])
        route_cur = cursor.fetchall()[0][0]
    else:
        route_cur = "0"
    query = 'SELECT name_long FROM stations WHERE station_id=%s'
    cursor.execute(query, [station_id])
    station = cursor.fetchall()[0][0]
    mysql_close(myconn, cursor)
    station_url = urls['station'] + str(station_id)
    try:
        r = requests.get(station_url,timeout=3)
    except:
        board = messages['answer_server_error']
        return board, route_cur, station
    soup = BeautifulSoup(r.text.encode('utf-8'), "lxml")
    routes_board, times_board, directions_board, disabled_board = [], [], [], []
    for routes_row in soup.find_all(href=re.compile("^\?mr_id=[0-9]+$")):
        routes_board.append(str(routes_row.text.strip()))
    for directions_row in soup.find_all(href=re.compile("^\?mr_id=[0-9]+&rl_racetype=[0-9]+$")):
        directions_board.append(re.sub('\(.*?\)', '', str(directions_row.text.strip())))
    for times_row in soup.find_all(href=re.compile("^\?srv_id=[0-9]&uniqueid=[0-9]+$")):
        parent_td = times_row.parent.parent
        if parent_td.find(nowrap='nowrap'):
            parent_td = times_row.parent.parent.parent.parent.parent
        times_board.append(str(times_row.text.strip()))
        if parent_td.find('img'):
            disabled_board.append(messages['board_disabled'])
        else:
            disabled_board.append('')
    board = "" 
    for index, route in enumerate(routes_board):
        if route in routes_active:
            if route == route_cur:
                board += "*" + messages['board_middle'] + times_board[index] + messages['board_prefix'] + route + messages['button_direction'] + directions_board[index] + disabled_board[index] + "*\n"
            elif index < 16:
                board += messages['board_middle'] + times_board[index] + messages['board_prefix'] + route + messages['button_direction'] + directions_board[index] + disabled_board[index] + "\n"
    return board, route_cur, station

def main_menu(routes):
    myconn, cursor = mysql_connect()
    markup, markup_line = [], []
    for index, route in enumerate(routes, 1):
        query = 'SELECT route_id FROM routes WHERE route=%s'
        cursor.execute(query, [route])
        route_id = cursor.fetchall()[0][0]
        markup_line.append(InlineKeyboardButton(route, callback_data='route,' + str(route_id) + ',' + route))
        if (index % 5 == 0) or (index == len(routes)):
            markup.append(markup_line)
            markup_line = []
    mysql_close(myconn, cursor)
    return InlineKeyboardMarkup(markup)

def directions_menu(route_id):
    myconn, cursor = mysql_connect()
    query = 'SELECT route FROM routes WHERE route_id=%s'
    cursor.execute(query, [route_id])
    route = cursor.fetchall()[0][0]
    query = 'SELECT endpoint_start_id,endpoint_end_id FROM routes WHERE route_id=%s'
    cursor.execute(query, [route_id])
    result = cursor.fetchall()
    station_start_id = result[0][0]
    station_end_id = result[0][1]
    query = 'SELECT name_short FROM stations WHERE station_id=%s'
    cursor.execute(query, [station_start_id])
    station_start_name = cursor.fetchall()[0][0]
    cursor.execute(query, [station_end_id])
    station_end_name = cursor.fetchall()[0][0]
    mysql_close(myconn, cursor)
    markup = []
    markup.append([InlineKeyboardButton(messages['button_direction'] + station_start_name, callback_data='direction,' + str(route_id) + ',1')])
    markup.append([InlineKeyboardButton(messages['button_direction'] + station_end_name, callback_data='direction,' + str(route_id) + ',0')])
    markup.append([InlineKeyboardButton(messages['button_start'], callback_data='start')])
    return InlineKeyboardMarkup(markup), route

def stations_menu(route_id, direction_id):
    myconn, cursor = mysql_connect()
    query = 'SELECT station_id FROM directions WHERE route_id=%s AND direction_id=%s'
    cursor.execute(query, [route_id, direction_id])
    station_ids = [item[0] for item in cursor.fetchall()]
    query = 'SELECT route FROM routes WHERE route_id=%s'
    cursor.execute(query, [route_id])
    route = cursor.fetchall()[0][0]
    markup, markup_line = [], []
    for index, station_id in enumerate(station_ids, 1):
        query = 'SELECT name_short FROM stations WHERE station_id=%s'
        cursor.execute(query, [str(station_id)])
        try:
            station_name_short = cursor.fetchall()[0][0]
        except:
            continue
        markup_line.append(InlineKeyboardButton(station_name_short, callback_data='station,' + str(station_id) + ',' + route_id))
        if (index % 2 == 0) or (index == len(station_ids)):
            markup.append(markup_line)
            markup_line = []
    mysql_close(myconn, cursor)
    markup.append([InlineKeyboardButton(messages['button_start'], callback_data='start')])
    reply_markup = InlineKeyboardMarkup(markup)
    return reply_markup, route

def get_routes_active():
    myconn, cursor = mysql_connect()
    routes_active_query = 'SELECT route FROM routes WHERE active = 1 ORDER BY route_int;'
    cursor.execute(routes_active_query)
    routes_active = [str(item[0]) for item in cursor.fetchall()]
    mysql_close(myconn, cursor)
    return routes_active

if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    logger = logging.getLogger(__name__)

    routes_active = get_routes_active()

    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start_callback))
    dispatcher.add_handler(CommandHandler("help", help_callback))
    updater.dispatcher.add_handler(MessageHandler(Filters.text, message_callback))
    dispatcher.add_handler(CallbackQueryHandler(query_callback))
    dispatcher.add_error_handler(error)
    updater.start_polling()
    updater.idle()

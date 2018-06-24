import logging
import re

from peewee import *
from telegram import (ChatAction, ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.ext import (Updater, CommandHandler, MessageHandler, ConversationHandler, RegexHandler, Filters)

from database import User, Card, DATABASE
from settings import (TOKEN, INFO_MESSAGE, INFO_MESSAGE_FOR_PRIVILEGE, WEBHOOK)
from solve_captcha import get_info_of_card

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

CHOOSING, CHECK_BALANCE, GET_INFO, SAVE_CARD, DELETE_CARD = range(5)
reply_keyboard = [['Проверить баланс', 'Посмотреть данные карты'], ['Сохранить карту', 'Удалить карту'], ['Выйти']]
MARKUP = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)


def start(bot, update):
    update.message.reply_text(
        'Привет! Что нужно сделать?', reply_markup=MARKUP)
    return CHOOSING


def help(bot, update):
    update.message.reply_text('Что нужно сделать?', reply_markup=MARKUP)
    return CHOOSING


def cancel(bot, update, user_data):
    update.message.reply_text('Что теперь?', reply_markup=MARKUP)
    return CHOOSING


def exit(bot, update, user_data):
    update.message.reply_text('Ок, пока.\n'
                              'Вы всегда можете снова запустить бота командой /start',
                              reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def get_saved_cards(update):
    cards_keyboard = []
    from_user = update.message.from_user
    user_id = str(from_user['id'])
    try:
        with DATABASE.atomic():
            user = User.get(User.user_id == user_id)
            if len(user.cards) == 0:
                return None
            for card in user.cards:
                cards_keyboard.append([card.card_number])
            cards_keyboard.append(['Отмена'])
            cards_markup = ReplyKeyboardMarkup(cards_keyboard, one_time_keyboard=True,
                                               resize_keyboard=True)
            return cards_markup
    except DoesNotExist:
        return None


def choose(bot, update, user_data):
    cards_keyboard = get_saved_cards(update)
    if cards_keyboard is None:
        update.message.reply_text('Ок, введите номер карты:')
    else:
        update.message.reply_text('Ок, введите номер карты или выберите существующую:',
                                  reply_markup=cards_keyboard)


def choosing_balance(bot, update, user_data):
    choose(bot, update, user_data)
    return CHECK_BALANCE


def choosing_info(bot, update, user_data):
    choose(bot, update, user_data)
    return GET_INFO


def choosing_save_card(bot, update, user_data):
    update.message.reply_text('Ок, введите номер карты или нажмите на /cancel чтобы отменить:')  # нельзя выйти
    return SAVE_CARD


def choosing_delete_card(bot, update, user_data):
    cards_keyboard = get_saved_cards(update)
    if cards_keyboard is None:
        update.message.reply_text('У вас нет сохраненных карт 😞')
        return cancel(None, update, None)
    else:
        update.message.reply_text('Ок, выберите карту:', reply_markup=cards_keyboard)
    return DELETE_CARD


def check_balance(bot, update, user_data):
    card_number = update.message.text
    user_id = update.message.from_user['id']
    message = update.message.reply_text('Получаем данные. Пожалуйста подождите...')
    update.message.chat.send_action(action=ChatAction.TYPING)
    balance = get_info_of_card(card_number, user_id)
    message.edit_text(balance)
    return cancel(None, update, None)


def get_info(bot, update, user_data):
    card_number = update.message.text
    user_id = update.message.from_user['id']
    message = update.message.reply_text('Получаем данные. Пожалуйста подождите...')
    update.message.chat.send_action(action=ChatAction.TYPING)
    info = get_info_of_card(card_number, user_id, all_info=True)
    if len(info) == 10 and isinstance(info, list):
        message.edit_text(INFO_MESSAGE.format(*info))
    elif len(info) == 8 and isinstance(info, list):
        message.edit_text(INFO_MESSAGE_FOR_PRIVILEGE.format(*info))
    else:
        message.edit_text(info)
    return cancel(None, update, None)


def save_card(bot, update, user_data):
    card_number = update.message.text
    check_card = re.match(r'\d{10,20}', card_number)
    message = 'Ок, карта {} сохранена 👌'.format(card_number)
    if check_card is None:
        message = 'Введен неверный номер карты 😞'
    from_user = update.message.from_user
    user_id = str(from_user['id'])
    try:
        with DATABASE.atomic():
            user = User.get(User.user_id == user_id)
            check_sum = user_id + card_number
            card = Card.create(card_number=card_number,
                               user=user,
                               check_sum=check_sum)
            card.save()
    except IntegrityError:
        message = 'Пользователь c такой картой уже существует 😞'
    except DoesNotExist:
        user = User.create(user_id=user_id,
                           first_name=from_user['first_name'],
                           last_name=from_user['last_name'])
        user.save()
    update.message.reply_text(message)
    return cancel(None, update, None)


def delete_card(bot, update, user_data):
    card_number = update.message.text
    try:
        with DATABASE.atomic():
            card = Card.get(Card.card_number == card_number)
            card.delete_instance()
            message = 'Ок, карта {} удалена 👌'.format(card.card_number)
    except DoesNotExist:
        message = 'То, что мертво, умереть не может.'
    update.message.reply_text(message)
    return cancel(None, update, None)


def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"', update, error)


def main():
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    help_handler = CommandHandler('help', help)
    cancel_handler = RegexHandler('^Отмена$|^/cancel$', cancel, pass_user_data=True)
    exit_handler = RegexHandler('^Выйти$', exit, pass_user_data=True)
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],

        states={
            CHOOSING: [cancel_handler,
                       RegexHandler('^Проверить баланс$',
                                    choosing_balance,
                                    pass_user_data=True),
                       RegexHandler('^Посмотреть данные карты$',
                                    choosing_info, pass_user_data=True),
                       RegexHandler('^Сохранить карту$',
                                    choosing_save_card, pass_user_data=True),
                       RegexHandler('^Удалить карту$',
                                    choosing_delete_card, pass_user_data=True)
                       ],

            CHECK_BALANCE: [cancel_handler,
                            MessageHandler(Filters.text,
                                           check_balance,
                                           pass_user_data=True)
                            ],
            GET_INFO: [cancel_handler,
                       MessageHandler(Filters.text,
                                      get_info,
                                      pass_user_data=True)
                       ],
            SAVE_CARD: [cancel_handler,
                        MessageHandler(Filters.text,
                                       save_card,
                                       pass_user_data=True)
                        ],
            DELETE_CARD: [cancel_handler,
                          MessageHandler(Filters.text,
                                         delete_card,
                                         pass_user_data=True)
                          ]
        },
        fallbacks=[exit_handler], allow_reentry=True
    )
    dispatcher.add_handler(conversation_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(cancel_handler)
    dispatcher.add_error_handler(error)
    updater.start_webhook(listen=WEBHOOK.get('listen'),
                          port=WEBHOOK.get('port'),
                          url_path=WEBHOOK.get('url_path'),
                          key=WEBHOOK.get('key'),
                          cert=WEBHOOK.get('cert'),
                          webhook_url=WEBHOOK.get('webhook_url'))
    updater.idle()


if __name__ == '__main__':
    main()

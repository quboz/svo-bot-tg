from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
import sqlite3
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = ''  #тут свой токен
ADMIN_ID = 6574083440 #тут свой айди тг для админа (узнать - @my_id_bot)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

#таблы
def create_tables():
    
    script_dir = os.path.dirname(os.path.abspath(__file__))  
    
    
    db_path = os.path.join(script_dir, 'users.db')

    
    if os.path.exists(db_path):
        print(f"База данных уже существует: {db_path}")
    else:
        print(f"База данных будет создана: {db_path}")
    
    #
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()

    try:
        # users
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,  
            full_name TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            consent BOOLEAN
        )
        ''')

        # requests
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            subcategory TEXT,
            description TEXT,
            file_id TEXT,
            status TEXT DEFAULT 'В ожидании',
            specialist_id INTEGER DEFAULT NULL,
            report_text TEXT DEFAULT NULL,
            report_photo TEXT DEFAULT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')

        
        cursor.execute('PRAGMA table_info(requests)')
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]

        if 'report_text' not in column_names:
            cursor.execute('ALTER TABLE requests ADD COLUMN report_text TEXT DEFAULT NULL')
            print("Столбец report_text добавлен в таблицу requests.")

        if 'report_photo' not in column_names:
            cursor.execute('ALTER TABLE requests ADD COLUMN report_photo TEXT DEFAULT NULL')
            print("Столбец report_photo добавлен в таблицу requests.")

        conn.commit()
        print(f"Таблицы созданы или обновлены успешно в: {db_path}")

    except sqlite3.Error as e:
        print(f"Ошибка при создании таблиц: {e}")

    finally:
        conn.close()


create_tables()


conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()



# рега
class RegistrationStates(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_phone = State()
    waiting_for_email = State()
    waiting_for_address = State()
    waiting_for_consent = State()

# создание
class RequestStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_subcategory = State()
    waiting_for_description = State()
    waiting_for_file = State()
    waiting_for_cancel_request = State()

# админка
class AdminStates(StatesGroup):
    waiting_for_request_id = State()  
    waiting_for_new_status = State()  
    waiting_for_request_id_for_specialist = State()  
    waiting_for_specialist_id = State()  

# спец
class SpecialistStates(StatesGroup):
    waiting_for_request_id_to_update = State()
    waiting_for_new_status = State()
    waiting_for_request_id_for_report = State()
    waiting_for_report_text = State()
    waiting_for_report_photo = State()

# стари
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    # есть ли в бд(проверка)
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (message.from_user.id,))
    user = cursor.fetchone()

    if not user:
        # нету в бд(начинается рега)
        await message.answer("Добро пожаловать! Давайте начнем регистрацию.\nВведите ваше ФИО:")
        await RegistrationStates.waiting_for_full_name.set()
    else:
        # если зареган=главное меню
        await show_main_menu(message)

# фио
@dp.message_handler(state=RegistrationStates.waiting_for_full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    # save
    await state.update_data(full_name=message.text)
    await message.answer("Спасибо! Теперь введите ваш номер телефона:")
    await RegistrationStates.waiting_for_phone.set()

# telefon
@dp.message_handler(state=RegistrationStates.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    # save
    await state.update_data(phone=message.text)
    await message.answer("Отлично! Теперь введите ваш email:")
    await RegistrationStates.waiting_for_email.set()

# email
@dp.message_handler(state=RegistrationStates.waiting_for_email)
async def process_email(message: types.Message, state: FSMContext):
    # save
    await state.update_data(email=message.text)
    await message.answer("Хорошо! Теперь введите ваш адрес:")
    await RegistrationStates.waiting_for_address.set()

# address
@dp.message_handler(state=RegistrationStates.waiting_for_address)
async def process_address(message: types.Message, state: FSMContext):
    # save
    await state.update_data(address=message.text)
    
    # dlya soglasiya knopki
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Согласен"), KeyboardButton("Не согласен"))
    
    # zapros
    await message.answer("Спасибо! Дайте согласие на обработку данных:", reply_markup=keyboard)
    
    await RegistrationStates.waiting_for_consent.set()

@dp.message_handler(state=RegistrationStates.waiting_for_consent)
async def process_consent(message: types.Message, state: FSMContext):
    consent = message.text.lower() in ["согласен", "согласна"]
    
    
    user_data = await state.get_data()
    user_id = message.from_user.id 
    
    try:
        # save v bd
        cursor.execute('''
        INSERT INTO users (user_id, full_name, phone, email, address, consent)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, user_data['full_name'], user_data['phone'], user_data['email'], user_data['address'], consent))
        conn.commit()
        
        # uved
        await message.answer("Регистрация завершена! Теперь вы можете создавать заявки.", reply_markup=types.ReplyKeyboardRemove())
        
        # main 
        await show_main_menu(message)
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при сохранении данных: {e}")

    
    await state.finish()

# main menu
async def show_main_menu(message: types.Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Создать заявку"))
    keyboard.add(KeyboardButton("Статус заявки"))
    if message.from_user.id == ADMIN_ID:
        keyboard.add(KeyboardButton("Админ-панель"))
    await message.answer("Выберите действие:", reply_markup=keyboard)

#отзывы не ворк
class FeedbackStates(StatesGroup):
    waiting_for_rating = State()  # Ожидание оценки
    waiting_for_feedback = State()  # Ожидание текстового отзыва






#отзывы не ворк
@dp.message_handler(state=FeedbackStates.waiting_for_rating)
async def process_rating(message: types.Message, state: FSMContext):
    logger.info(f"Получено сообщение: {message.text}")
    rating_text = message.text

    if rating_text in ["1 ⭐", "2 ⭐⭐", "3 ⭐⭐⭐", "4 ⭐⭐⭐⭐", "5 ⭐⭐⭐⭐⭐"]:
        rating = int(rating_text[0])
        logger.info(f"Оценка {rating} принята.")

        user_data = await state.get_data()
        request_id = user_data['request_id']
        logger.info(f"ID заявки: {request_id}")

        try:
            # Сохраняем оценку в базу данных
            cursor.execute('''
            INSERT INTO ratings (request_id, user_id, rating)
            VALUES (?, ?, ?)
            ''', (request_id, message.from_user.id, rating))
            conn.commit()
            logger.info("Оценка сохранена в базу данных.")
            await message.answer("Спасибо за вашу оценку!", reply_markup=types.ReplyKeyboardRemove())
        except sqlite3.Error as e:
            logger.error(f"Ошибка при сохранении оценки: {e}")
            await message.answer(f"Ошибка при сохранении оценки: {e}")
    else:
        logger.warning(f"Некорректный ввод: {rating_text}")
        await message.answer("Пожалуйста, выберите оценку от 1 до 5 с помощью кнопок.", reply_markup=get_rating_keyboard())

    await state.finish()


#заявки
@dp.message_handler(lambda message: message.text == "Статус заявки" and message.from_user.id != ADMIN_ID)
async def show_request_status(message: types.Message):
    user_id = message.from_user.id
    try:
        
        cursor.execute('''
        SELECT id, status FROM requests WHERE user_id = ?
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
            response = "Статус ваших заявок:\n\n"
            for req in requests:
                response += (
                    f"Заявка #{req[0]}\n"
                    f"Статус: {req[1]}\n\n"
                )
            await message.answer(response, reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))
        else:
            await message.answer("У вас пока нет заявок.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении статуса заявок: {e}", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))


# гм для адм
async def show_admin_menu(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Просмотреть все заявки"))
    keyboard.add(types.KeyboardButton("Назначить специалиста"))
    keyboard.add(types.KeyboardButton("Изменить статус заявки"))
    keyboard.add(types.KeyboardButton("Пользовательский интерфейс"))
    await message.answer("Админ-панель. Выберите действие:", reply_markup=keyboard)

# спец
async def show_specialist_menu(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Мои заявки"))
    keyboard.add(types.KeyboardButton("Изменить статус заявки"))
    keyboard.add(types.KeyboardButton("Предоставить отчёт"))
    await message.answer("Меню специалиста. Выберите действие:", reply_markup=keyboard)




# назад
@dp.message_handler(lambda message: message.text == "Назад" and message.from_user.id != ADMIN_ID)
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await state.finish()  
    await show_specialist_menu(message)  


@dp.message_handler(lambda message: message.text == "Назад" and message.from_user.id != ADMIN_ID)
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await state.finish()  
    await show_main_menu(message)  


# мои заявки
@dp.message_handler(lambda message: message.text == "Мои заявки" and message.from_user.id != ADMIN_ID)
async def show_my_requests_as_specialist(message: types.Message):
    user_id = message.from_user.id
    try:
        # заявы для спеца
        cursor.execute('''
        SELECT id, user_id, category, subcategory, description, status FROM requests WHERE specialist_id = ?
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
            response = "Ваши заявки:\n\n"
            for req in requests:
                response += (
                    f"Заявка #{req[0]}\n"
                    f"Пользователь: {req[1]}\n"
                    f"Категория: {req[2]}\n"
                    f"Подкатегория: {req[3]}\n"
                    f"Описание: {req[4]}\n"
                    f"Статус: {req[5]}\n\n"
                )
            await message.answer(response, reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))
        else:
            await message.answer("У вас пока нет назначенных заявок.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))

# актив заявки для спеца
@dp.message_handler(lambda message: message.text == "Активные заявки" and message.from_user.id != ADMIN_ID)
async def show_active_requests_as_specialist(message: types.Message):
    user_id = message.from_user.id
    try:
        
        cursor.execute('''
        SELECT id, user_id, category, subcategory, description, status FROM requests WHERE specialist_id = ? AND status != 'Выполнено'
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
            response = "Ваши активные заявки:\n\n"
            for req in requests:
                response += (
                    f"Заявка #{req[0]}\n"
                    f"Пользователь: {req[1]}\n"
                    f"Категория: {req[2]}\n"
                    f"Подкатегория: {req[3]}\n"
                    f"Описание: {req[4]}\n"
                    f"Статус: {req[5]}\n\n"
                )
            await message.answer(response)
        else:
            await message.answer("У вас пока нет активных заявок.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}")

# выполненые заявки для спеца
@dp.message_handler(lambda message: message.text == "Выполненные заявки" and message.from_user.id != ADMIN_ID)
async def show_completed_requests_as_specialist(message: types.Message):
    user_id = message.from_user.id
    try:
       
        cursor.execute('''
        SELECT id, user_id, category, subcategory, description, status FROM requests WHERE specialist_id = ? AND status = 'Выполнено'
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
            response = "Ваши выполненные заявки:\n\n"
            for req in requests:
                response += (
                    f"Заявка #{req[0]}\n"
                    f"Пользователь: {req[1]}\n"
                    f"Категория: {req[2]}\n"
                    f"Подкатегория: {req[3]}\n"
                    f"Описание: {req[4]}\n"
                    f"Статус: {req[5]}\n\n"
                )
            await message.answer(response)
        else:
            await message.answer("У вас пока нет выполненных заявок.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}")

# изменить статус
@dp.message_handler(lambda message: message.text == "Изменить статус заявки" and message.from_user.id == ADMIN_ID)
async def change_request_status_start_admin(message: types.Message):
    await message.answer("Введите номер заявки, статус которой хотите изменить:")
    await AdminStates.waiting_for_request_id.set()

# номер 
@dp.message_handler(state=AdminStates.waiting_for_request_id)
async def process_request_id_to_update_admin(message: types.Message, state: FSMContext):
    try:
        request_id = int(message.text)
        await state.update_data(request_id=request_id)

        # новый статус
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.KeyboardButton("В ожидании"))
        keyboard.add(types.KeyboardButton("В работе"))
        keyboard.add(types.KeyboardButton("Выполнено"))
        await message.answer("Выберите новый статус:", reply_markup=keyboard)
        await AdminStates.waiting_for_new_status.set()
    except ValueError:
        await message.answer("Пожалуйста, введите номер заявки (число).")
        await state.finish()

# выбор статуса
@dp.message_handler(state=AdminStates.waiting_for_new_status)
async def process_new_status_admin(message: types.Message, state: FSMContext):
    new_status = message.text
    user_data = await state.get_data()
    request_id = user_data['request_id']

    try:
        # обнова статуса
        cursor.execute('''
        UPDATE requests SET status = ? WHERE id = ?
        ''', (new_status, request_id))
        conn.commit()

        
        cursor.execute('SELECT user_id FROM requests WHERE id = ?', (request_id,))
        user_id = cursor.fetchone()[0]

        
        await bot.send_message(user_id, f"Статус вашей заявки #{request_id} изменён на: {new_status}.")

        await message.answer(f"Статус заявки #{request_id} успешно изменён на: {new_status}.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при изменении статуса: {e}")

    await state.finish()
    await show_admin_menu(message)

# изменить статус
@dp.message_handler(lambda message: message.text == "Изменить статус заявки" and message.from_user.id != ADMIN_ID)
async def change_request_status_start(message: types.Message):
    user_id = message.from_user.id
    try:
        
        cursor.execute('''
        SELECT id FROM requests WHERE specialist_id = ?
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
            
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for req in requests:
                keyboard.add(types.KeyboardButton(f"Заявка #{req[0]}"))
            keyboard.add("Назад") 
            await message.answer("Выберите заявку для изменения статуса:", reply_markup=keyboard)
            await SpecialistStates.waiting_for_request_id_to_update.set()
        else:
            await message.answer("У вас пока нет назначенных заявок.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))


@dp.message_handler(state=SpecialistStates.waiting_for_request_id_to_update)
async def process_request_id_to_update(message: types.Message, state: FSMContext):
    try:
        request_id = int(message.text.split('#')[1])  
        await state.update_data(request_id=request_id)

        
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.KeyboardButton("В ожидании"))
        keyboard.add(types.KeyboardButton("В работе"))
        keyboard.add(types.KeyboardButton("Выполнено"))
        await message.answer("Выберите новый статус:", reply_markup=keyboard)
        await SpecialistStates.waiting_for_new_status.set()
    except (ValueError, IndexError):
        await message.answer("Пожалуйста, выберите заявку из списка.")
        await state.finish()



# отчет
@dp.message_handler(lambda message: message.text == "Предоставить отчёт" and message.from_user.id != ADMIN_ID)
async def provide_report_start(message: types.Message):
    user_id = message.from_user.id
    try:
        
        cursor.execute('''
        SELECT id FROM requests WHERE specialist_id = ?
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
        
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for req in requests:
                keyboard.add(types.KeyboardButton(f"Заявка #{req[0]}"))
            keyboard.add("Назад")  
            await message.answer("Выберите заявку для предоставления отчёта:", reply_markup=keyboard)
            await SpecialistStates.waiting_for_request_id_for_report.set()
        else:
            await message.answer("У вас пока нет назначенных заявок.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))


@dp.message_handler(state=SpecialistStates.waiting_for_request_id_for_report)
async def process_request_id_for_report(message: types.Message, state: FSMContext):
    try:
        request_id = int(message.text.split('#')[1])  
        await state.update_data(request_id=request_id)

        await message.answer("Введите текстовый отчёт о выполненной работе:")
        await SpecialistStates.waiting_for_report_text.set()
    except (ValueError, IndexError):
        await message.answer("Пожалуйста, выберите заявку из списка.")
        await state.finish()


@dp.message_handler(state=SpecialistStates.waiting_for_report_text)
async def process_report_text(message: types.Message, state: FSMContext):
    await state.update_data(report_text=message.text)
    await message.answer("При необходимости прикрепите фотоотчёт:")
    await SpecialistStates.waiting_for_report_photo.set()


@dp.message_handler(content_types=types.ContentType.PHOTO, state=SpecialistStates.waiting_for_report_photo)
async def process_report_photo(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    request_id = user_data['request_id']
    report_text = user_data['report_text']
    report_photo = message.photo[-1].file_id

    try:
       
        cursor.execute('''
        UPDATE requests SET report_text = ?, report_photo = ?, status = 'Выполнено' WHERE id = ?
        ''', (report_text, report_photo, request_id))
        conn.commit()

        
        cursor.execute('SELECT user_id FROM requests WHERE id = ?', (request_id,))
        user_id = cursor.fetchone()[0]

        
        await bot.send_message(user_id, f"Отчёт по вашей заявке #{request_id}:\n\n{report_text}")
        if report_photo:
            await bot.send_photo(user_id, report_photo)

        await message.answer("Отчёт успешно предоставлен и отправлен пользователю.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при предоставлении отчёта: {e}")

    await state.finish()
    await show_specialist_menu(message)

# 
@dp.message_handler(state=SpecialistStates.waiting_for_report_photo)
async def process_report_photo_text(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    request_id = user_data['request_id']
    report_text = user_data['report_text']

    try:
        
        cursor.execute('''
        UPDATE requests SET report_text = ?, status = 'Выполнено' WHERE id = ?
        ''', (report_text, request_id))
        conn.commit()

       
        cursor.execute('SELECT user_id FROM requests WHERE id = ?', (request_id,))
        user_id = cursor.fetchone()[0]

        
        await bot.send_message(user_id, f"Отчёт по вашей заявке #{request_id}:\n\n{report_text}")

        await message.answer("Отчёт успешно предоставлен и отправлен пользователю.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при предоставлении отчёта: {e}")

    await state.finish()
    await show_specialist_menu(message)

# старт
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await show_admin_menu(message)
    else:
        # спец не спец
        cursor.execute('SELECT id FROM requests WHERE specialist_id = ?', (message.from_user.id,))
        if cursor.fetchone():
            await show_specialist_menu(message)
        else:
            await message.answer("Добро пожаловать! Давайте начнем регистрацию.\nВведите ваше ФИО:")
            await RegistrationStates.waiting_for_full_name.set()



# гм админ
async def show_admin_menu(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Просмотреть все заявки"))
    keyboard.add(types.KeyboardButton("Назначить специалиста"))
    keyboard.add(types.KeyboardButton("Пользовательский интерфейс"))
    await message.answer("Админ-панель. Выберите действие:", reply_markup=keyboard)

# м для п
async def show_main_menu(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Создать заявку"))
    keyboard.add(types.KeyboardButton("Статус заявки"))  # Новая кнопка
    if message.from_user.id == ADMIN_ID:
        keyboard.add(types.KeyboardButton("Админ-панель"))
    await message.answer("Выберите действие:", reply_markup=keyboard)

# м для спец
async def show_specialist_menu(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Мои заявки"))
    keyboard.add(types.KeyboardButton("Изменить статус заявки"))
    keyboard.add(types.KeyboardButton("Предоставить отчёт"))
    keyboard.add(types.KeyboardButton("Назад"))
    await message.answer("Меню специалиста. Выберите действие:", reply_markup=keyboard)





# моизаявки
@dp.message_handler(lambda message: message.text == "Мои заявки" and message.from_user.id != ADMIN_ID)
async def show_my_requests(message: types.Message):
    user_id = message.from_user.id
    try:
        cursor.execute('''
        SELECT id, category, subcategory, description, status FROM requests WHERE user_id = ?
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
            response = "Ваши заявки:\n\n"
            for req in requests:
                response += (
                    f"Заявка #{req[0]}\n"
                    f"Категория: {req[1]}\n"
                    f"Подкатегория: {req[2]}\n"
                    f"Описание: {req[3]}\n"
                    f"Статус: {req[4]}\n\n"
                )
            await message.answer(response, reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))
        else:
            await message.answer("У вас пока нет заявок.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))


@dp.message_handler(lambda message: message.text == "Завершённые заявки" and message.from_user.id != ADMIN_ID)
async def show_completed_requests_as_specialist(message: types.Message):
    user_id = message.from_user.id
    try:
        
        cursor.execute('''
        SELECT id, user_id, category, subcategory, description, status FROM requests WHERE specialist_id = ? AND status = 'Выполнено'
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
            response = "Ваши завершённые заявки:\n\n"
            for req in requests:
                response += (
                    f"Заявка #{req[0]}\n"
                    f"Пользователь: {req[1]}\n"
                    f"Категория: {req[2]}\n"
                    f"Подкатегория: {req[3]}\n"
                    f"Описание: {req[4]}\n"
                    f"Статус: {req[5]}\n\n"
                )
            await message.answer(response)
        else:
            await message.answer("У вас пока нет завершённых заявок.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}")



# ввод заявки
@dp.message_handler(state=SpecialistStates.waiting_for_request_id_to_update)
async def process_request_id_to_update(message: types.Message, state: FSMContext):
    try:
        request_id = int(message.text)
        await state.update_data(request_id=request_id)

        # заявка спецу
        cursor.execute('SELECT id FROM requests WHERE id = ? AND specialist_id = ?', (request_id, message.from_user.id))
        if cursor.fetchone():
            # выбор нового статуса
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(types.KeyboardButton("В ожидании"))
            keyboard.add(types.KeyboardButton("В работе"))
            keyboard.add(types.KeyboardButton("Выполнено"))
            await message.answer("Выберите новый статус:", reply_markup=keyboard)
            await SpecialistStates.waiting_for_new_status.set()
        else:
            await message.answer("Заявка с таким номером не найдена или не назначена вам.")
            await state.finish()
    except ValueError:
        await message.answer("Пожалуйста, введите номер заявки (число).")
        await state.finish()

#  новый статус
@dp.message_handler(state=SpecialistStates.waiting_for_new_status)
async def process_new_status(message: types.Message, state: FSMContext):
    new_status = message.text
    user_data = await state.get_data()
    request_id = user_data['request_id']

    try:
        
        cursor.execute('''
        UPDATE requests SET status = ? WHERE id = ?
        ''', (new_status, request_id))
        conn.commit()

        
        cursor.execute('SELECT user_id FROM requests WHERE id = ?', (request_id,))
        user_id = cursor.fetchone()[0]

        
        await bot.send_message(user_id, f"Статус вашей заявки #{request_id} изменён на: {new_status}.")

        
        if new_status == "Выполнено":
            logger.info("Предложение оставить оценку...")
            await bot.send_message(user_id, "Пожалуйста, оцените выполнение заявки от 1 до 5:", reply_markup=get_rating_keyboard())
            await FeedbackStates.waiting_for_rating.set()  
        else:
            await message.answer(f"Статус заявки #{request_id} успешно изменён на: {new_status}.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при изменении статуса: {e}")

    await state.finish()

# предоставить отчет
@dp.message_handler(lambda message: message.text == "Предоставить отчёт" and message.from_user.id != ADMIN_ID)
async def provide_report_start(message: types.Message):
    user_id = message.from_user.id
    try:
        
        cursor.execute('''
        SELECT id FROM requests WHERE specialist_id = ?
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
            
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for req in requests:
                keyboard.add(types.KeyboardButton(f"Заявка #{req[0]}"))
            keyboard.add("Назад")  
            await message.answer("Выберите заявку для предоставления отчёта:", reply_markup=keyboard)
            await SpecialistStates.waiting_for_request_id_for_report.set()
        else:
            await message.answer("У вас пока нет назначенных заявок.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))

# nomer zayav
@dp.message_handler(state=SpecialistStates.waiting_for_request_id_to_update)
async def process_request_id_for_report(message: types.Message, state: FSMContext):
    try:
        request_id = int(message.text)
        await state.update_data(request_id=request_id)

        
        cursor.execute('SELECT id FROM requests WHERE id = ? AND specialist_id = ?', (request_id, message.from_user.id))
        if cursor.fetchone():
            await message.answer("Введите текстовый отчёт о выполненной работе:")
            await SpecialistStates.waiting_for_report_text.set()
        else:
            await message.answer("Заявка с таким номером не найдена или не назначена вам.")
            await state.finish()
    except ValueError:
        await message.answer("Пожалуйста, введите номер заявки (число).")
        await state.finish()


@dp.message_handler(state=SpecialistStates.waiting_for_report_text)
async def process_report_text(message: types.Message, state: FSMContext):
    await state.update_data(report_text=message.text)
    await message.answer("При необходимости прикрепите фотоотчёт:")
    await SpecialistStates.waiting_for_report_photo.set()


@dp.message_handler(content_types=types.ContentType.PHOTO, state=SpecialistStates.waiting_for_report_photo)
async def process_report_photo(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    request_id = user_data['request_id']
    report_text = user_data['report_text']
    report_photo = message.photo[-1].file_id

    try:
        
        cursor.execute('''
        UPDATE requests SET report_text = ?, report_photo = ?, status = 'Выполнено' WHERE id = ?
        ''', (report_text, report_photo, request_id))
        conn.commit()

        
        cursor.execute('SELECT user_id FROM requests WHERE id = ?', (request_id,))
        user_id = cursor.fetchone()[0]

        
        await bot.send_message(user_id, f"Отчёт по вашей заявке #{request_id}:\n\n{report_text}")
        if report_photo:
            await bot.send_photo(user_id, report_photo)

        await message.answer("Отчёт успешно предоставлен и отправлен пользователю.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при предоставлении отчёта: {e}")

    await state.finish()
    await show_specialist_menu(message)


@dp.message_handler(state=SpecialistStates.waiting_for_report_photo)
async def process_report_photo_text(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    request_id = user_data['request_id']
    report_text = user_data['report_text']

    try:
       
        cursor.execute('''
        UPDATE requests SET report_text = ?, status = 'Выполнено' WHERE id = ?
        ''', (report_text, request_id))
        conn.commit()

        
        cursor.execute('SELECT user_id FROM requests WHERE id = ?', (request_id,))
        user_id = cursor.fetchone()[0]

        
        await bot.send_message(user_id, f"Отчёт по вашей заявке #{request_id}:\n\n{report_text}")

        await message.answer("Отчёт успешно предоставлен и отправлен пользователю.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при предоставлении отчёта: {e}")

    await state.finish()
    await show_specialist_menu(message)



@dp.message_handler(lambda message: message.text == "Создать заявку")
async def create_request(message: types.Message):
    
    categories_keyboard = types.InlineKeyboardMarkup(row_width=1)
    categories_keyboard.add(
        types.InlineKeyboardButton("Компьютер/ноутбук", callback_data="category_computer"),
        types.InlineKeyboardButton("Программное обеспечение", callback_data="category_software"),
        types.InlineKeyboardButton("Периферийные устройства", callback_data="category_peripheral")
    )
    await message.answer("Выберите категорию проблемы:", reply_markup=categories_keyboard)
    await RequestStates.waiting_for_category.set()

# category
@dp.callback_query_handler(lambda c: c.data.startswith('category_'), state=RequestStates.waiting_for_category)
async def process_category(callback_query: types.CallbackQuery, state: FSMContext):
    category = callback_query.data.split('_')[1]
    await state.update_data(category=category)

    # subcategory
    subcategories_keyboard = types.InlineKeyboardMarkup(row_width=1)

    if category == "computer":
        subcategories_keyboard.add(
            types.InlineKeyboardButton("Не включается", callback_data="subcategory_not_turning_on"),
            types.InlineKeyboardButton("Медленно работает", callback_data="subcategory_slow_performance"),
            types.InlineKeyboardButton("Зависает", callback_data="subcategory_freezing")
        )
    elif category == "software":
        subcategories_keyboard.add(
            types.InlineKeyboardButton("Помощь с установкой программ", callback_data="subcategory_install_software"),
            types.InlineKeyboardButton("Проверить/почистить от вирусов", callback_data="subcategory_virus_check"),
            types.InlineKeyboardButton("Не запускается/вылетает программа", callback_data="subcategory_program_crash"),
            types.InlineKeyboardButton("Установка/переустановка ОС", callback_data="subcategory_os_install")
        )
    elif category == "peripheral":
        subcategories_keyboard.add(
            types.InlineKeyboardButton("Подключить/настроить принтер", callback_data="subcategory_printer_setup"),
            types.InlineKeyboardButton("Клавиатура/мышь не работает", callback_data="subcategory_input_devices")
        )

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "Выберите подкатегорию:", reply_markup=subcategories_keyboard)
    await RequestStates.waiting_for_subcategory.set()


@dp.callback_query_handler(lambda c: c.data.startswith('subcategory_'), state=RequestStates.waiting_for_subcategory)
async def process_subcategory(callback_query: types.CallbackQuery, state: FSMContext):
    subcategory = callback_query.data.split('_')[1]
    await state.update_data(subcategory=subcategory)
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "Опишите вашу проблему:")
    await RequestStates.waiting_for_description.set()


@dp.message_handler(state=RequestStates.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("При необходимости прикрепите файл:")
    await RequestStates.waiting_for_file.set()


@dp.message_handler(state=RequestStates.waiting_for_file)
async def process_file(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    file_id = None

    if message.document:
        file_id = message.document.file_id
        await message.answer(f"Документ принят: {message.document.file_name}")
    elif message.photo:
        file_id = message.photo[-1].file_id
        await message.answer("Фото принято.")
    else:
        await message.answer("Прикрепите фото/документ.")

    try:
        
        cursor.execute('''
        INSERT INTO requests (user_id, category, subcategory, description, file_id)
        VALUES (?, ?, ?, ?, ?)
        ''', (message.from_user.id, user_data['category'], user_data['subcategory'], user_data['description'], file_id))
        conn.commit()

        
        request_id = cursor.lastrowid

       
        await bot.send_message(
            ADMIN_ID,
            f"Создана новая заявка #{request_id}:\n\n"
            f"Категория: {user_data['category']}\n"
            f"Подкатегория: {user_data['subcategory']}\n"
            f"Описание: {user_data['description']}"
        )

        await message.answer("Ваша заявка успешно создана!")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при сохранении заявки: {e}")

    await show_main_menu(message)
    await state.finish()

@dp.message_handler(state=RequestStates.waiting_for_file)
async def process_file_text(message: types.Message, state: FSMContext):
    user_data = await state.get_data()

    try:
        
        cursor.execute('''
        INSERT INTO requests (user_id, category, subcategory, description)
        VALUES (?, ?, ?, ?)
        ''', (message.from_user.id, user_data['category'], user_data['subcategory'], user_data['description']))
        conn.commit()

        
        request_id = cursor.lastrowid

       
        await bot.send_message(
            ADMIN_ID,
            f"Создана новая заявка #{request_id}:\n\n"
            f"Категория: {user_data['category']}\n"
            f"Подкатегория: {user_data['subcategory']}\n"
            f"Описание: {user_data['description']}"
        )

        await message.answer("Ваша заявка успешно создана!")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при сохранении заявки: {e}")

    await show_main_menu(message)
    await state.finish()




@dp.message_handler(lambda message: message.text == "Активные заявки" and message.from_user.id != ADMIN_ID)
async def show_active_requests(message: types.Message):
    user_id = message.from_user.id
    try:
        
        cursor.execute('''
        SELECT id, category, subcategory, description, status FROM requests WHERE user_id = ? AND status != 'Выполнено'
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
            response = "Ваши активные заявки:\n\n"
            for req in requests:
                response += (
                    f"Заявка #{req[0]}\n"
                    f"Категория: {req[1]}\n"
                    f"Подкатегория: {req[2]}\n"
                    f"Описание: {req[3]}\n"
                    f"Статус: {req[4]}\n\n"
                )
            await message.answer(response)
        else:
            await message.answer("У вас пока нет активных заявок.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}")


@dp.message_handler(lambda message: message.text == "Выполненные заявки" and message.from_user.id != ADMIN_ID)
async def show_completed_requests(message: types.Message):
    user_id = message.from_user.id
    try:
       
        cursor.execute('''
        SELECT id, category, subcategory, description, status FROM requests WHERE user_id = ? AND status = 'Выполнено'
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
            response = "Ваши выполненные заявки:\n\n"
            for req in requests:
                response += (
                    f"Заявка #{req[0]}\n"
                    f"Категория: {req[1]}\n"
                    f"Подкатегория: {req[2]}\n"
                    f"Описание: {req[3]}\n"
                    f"Статус: {req[4]}\n\n"
                )
            await message.answer(response)
        else:
            await message.answer("У вас пока нет выполненных заявок.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}")


@dp.message_handler(lambda message: message.text == "Мои заявки" and message.from_user.id != ADMIN_ID)
async def show_my_requests(message: types.Message):
    user_id = message.from_user.id
    try:
        
        cursor.execute('''
        SELECT id, category, subcategory, description, status FROM requests WHERE user_id = ?
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
            response = "Ваши заявки:\n\n"
            for req in requests:
                response += (
                    f"Заявка #{req[0]}\n"
                    f"Категория: {req[1]}\n"
                    f"Подкатегория: {req[2]}\n"
                    f"Описание: {req[3]}\n"
                    f"Статус: {req[4]}\n\n"
                )
            await message.answer(response, reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))
        else:
            await message.answer("У вас пока нет заявок.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Назад"))


@dp.message_handler(lambda message: message.text == "Активные заявки" and message.from_user.id != ADMIN_ID)
async def show_active_requests_as_specialist(message: types.Message):
    user_id = message.from_user.id
    try:
        
        cursor.execute('''
        SELECT id, user_id, category, subcategory, description, status FROM requests WHERE specialist_id = ? AND status != 'Выполнено'
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
            response = "Ваши активные заявки:\n\n"
            for req in requests:
                response += (
                    f"Заявка #{req[0]}\n"
                    f"Пользователь: {req[1]}\n"
                    f"Категория: {req[2]}\n"
                    f"Подкатегория: {req[3]}\n"
                    f"Описание: {req[4]}\n"
                    f"Статус: {req[5]}\n\n"
                )
            await message.answer(response)
        else:
            await message.answer("У вас пока нет активных заявок.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}")


@dp.message_handler(lambda message: message.text == "Выполненные заявки" and message.from_user.id != ADMIN_ID)
async def show_completed_requests_as_specialist(message: types.Message):
    user_id = message.from_user.id
    try:
        
        cursor.execute('''
        SELECT id, user_id, category, subcategory, description, status FROM requests WHERE specialist_id = ? AND status = 'Выполнено'
        ''', (user_id,))
        requests = cursor.fetchall()

        if requests:
            response = "Ваши выполненные заявки:\n\n"
            for req in requests:
                response += (
                    f"Заявка #{req[0]}\n"
                    f"Пользователь: {req[1]}\n"
                    f"Категория: {req[2]}\n"
                    f"Подкатегория: {req[3]}\n"
                    f"Описание: {req[4]}\n"
                    f"Статус: {req[5]}\n\n"
                )
            await message.answer(response)
        else:
            await message.answer("У вас пока нет выполненных заявок.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}")


@dp.message_handler(lambda message: message.text == "Изменить статус заявки" and message.from_user.id == ADMIN_ID)
async def change_request_status_start_admin(message: types.Message):
    await message.answer("Введите номер заявки, статус которой хотите изменить:")
    await AdminStates.waiting_for_request_id.set()


@dp.message_handler(state=AdminStates.waiting_for_request_id)
async def process_request_id_to_update_admin(message: types.Message, state: FSMContext):
    try:
        request_id = int(message.text)
        await state.update_data(request_id=request_id)

        
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.KeyboardButton("В ожидании"))
        keyboard.add(types.KeyboardButton("В работе"))
        keyboard.add(types.KeyboardButton("Выполнено"))
        await message.answer("Выберите новый статус:", reply_markup=keyboard)
        await AdminStates.waiting_for_new_status.set()
    except ValueError:
        await message.answer("Пожалуйста, введите номер заявки (число).")
        await state.finish()


@dp.message_handler(state=AdminStates.waiting_for_new_status)
async def process_new_status_admin(message: types.Message, state: FSMContext):
    new_status = message.text
    user_data = await state.get_data()
    request_id = user_data['request_id']

    try:
        
        cursor.execute('''
        UPDATE requests SET status = ? WHERE id = ?
        ''', (new_status, request_id))
        conn.commit()

        
        cursor.execute('SELECT user_id FROM requests WHERE id = ?', (request_id,))
        user_id = cursor.fetchone()[0]


        await bot.send_message(user_id, f"Статус вашей заявки #{request_id} изменён на: {new_status}.")

        await message.answer(f"Статус заявки #{request_id} успешно изменён на: {new_status}.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при изменении статуса: {e}")

    await state.finish()
    await show_admin_menu(message)

# otmena 
@dp.message_handler(state=RequestStates.waiting_for_cancel_request)
async def cancel_request(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        request_id = int(message.text)  

        # check
        cursor.execute('''
        SELECT id FROM requests WHERE id = ? AND user_id = ?
        ''', (request_id, user_id))
        request = cursor.fetchone()

        if request:
            # \del
            cursor.execute('''
            DELETE FROM requests WHERE id = ? AND user_id = ?
            ''', (request_id, user_id))
            conn.commit()
            await message.answer(f"Заявка #{request_id} успешно отменена.")
        else:
            await message.answer("Заявка с таким номером не найдена или не принадлежит вам.")
    except ValueError:
        await message.answer("Пожалуйста, введите номер заявки (число).")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при отмене заявки: {e}")

    await state.finish()
    await show_main_menu(message)

#adm panel
@dp.message_handler(lambda message: message.text == "Админ-панель" and message.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    await show_admin_menu(message)
#polz int
@dp.message_handler(lambda message: message.text == "Пользовательский интерфейс" and message.from_user.id == ADMIN_ID)
async def user_interface(message: types.Message):
    await show_main_menu(message)


@dp.message_handler(lambda message: message.text == "Просмотреть все заявки" and message.from_user.id == ADMIN_ID)
async def view_all_requests(message: types.Message):
    try:
        cursor.execute('''
        SELECT id, user_id, category, subcategory, description, status, specialist_id FROM requests
        ''')
        requests = cursor.fetchall()

        if requests:
            response = "Все заявки:\n\n"
            for req in requests:
                response += (
                    f"Заявка #{req[0]}\n"
                    f"Пользователь: {req[1]}\n"
                    f"Категория: {req[2]}\n"
                    f"Подкатегория: {req[3]}\n"
                    f"Описание: {req[4]}\n"
                    f"Статус: {req[5]}\n"
                    f"Специалист: {req[6] if req[6] else 'Не назначен'}\n\n"
                )
            await message.answer(response)
        else:
            await message.answer("Заявок пока нет.")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при получении заявок: {e}")


@dp.message_handler(lambda message: message.text == "Назначить специалиста" and message.from_user.id == ADMIN_ID)
async def assign_specialist_start(message: types.Message):
    await message.answer("Введите номер заявки:")
    await AdminStates.waiting_for_request_id_for_specialist.set()


@dp.message_handler(state=AdminStates.waiting_for_request_id_for_specialist)
async def process_request_id_for_specialist(message: types.Message, state: FSMContext):
    try:
        request_id = int(message.text)
        await state.update_data(request_id=request_id)

        await message.answer("Введите ID специалиста:")
        await AdminStates.waiting_for_specialist_id.set()
    except ValueError:
        await message.answer("Пожалуйста, введите номер заявки (число).")
        await state.finish()



@dp.message_handler(state=AdminStates.waiting_for_specialist_id)
async def process_specialist_id(message: types.Message, state: FSMContext):
    try:
        specialist_id = int(message.text)
        user_data = await state.get_data()
        request_id = user_data['request_id']

        
        cursor.execute('''
        UPDATE requests SET specialist_id = ?, status = 'В работе' WHERE id = ?
        ''', (specialist_id, request_id))
        conn.commit()

    
        await bot.send_message(specialist_id, f"Вам назначена новая заявка #{request_id}.")

        await message.answer(f"Специалист {specialist_id} назначен на заявку #{request_id}.")
    except ValueError:
        await message.answer("Пожалуйста, введите ID специалиста (число).")
    except sqlite3.Error as e:
        await message.answer(f"Ошибка при назначении специалиста: {e}")

    await state.finish()
    await show_admin_menu(message)


#очистка всех заявок
@dp.message_handler(commands=['clear_zayav'])
async def clear_requests(message: types.Message):
    
    if message.from_user.id == ADMIN_ID:
        try:
            cursor.execute('DELETE FROM requests')
            conn.commit()
            await message.answer("Все заявки успешно удалены.")
        except sqlite3.Error as e:
            await message.answer(f"Ошибка при удалении заявок: {e}")
    else:
        await message.answer("У вас нет прав для выполнения этой команды.")


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
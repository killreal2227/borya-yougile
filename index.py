import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


PILOT_TASKS = (
    "67f7d0b4-dbf4-46a2-bab2-9ec9db2e5068",
    "cecd2b06-b5bc-4fe1-9790-8493df824d7d",
)
PILOT_COLUMN = "17d46fae-46ad-4196-befb-d6dcc16c77c2"
YOUGILE = "https://yougile.com/api-v2/"
OWNER_USER_ID = "42766e6a-9ef8-490c-b24f-c81c937a4617"
MANAGER_USER_ID = "f3576ee6-911b-4795-bc8d-a1de057e70f2"
WORK_COLUMNS = (
    "e1f4d795-3963-4854-ba5e-e2e0e88455a8",
    "38466194-2701-4661-a674-b1a21adeebaa",
)
WORK_TASKS = (
    "f8fb891b-4792-44c6-bd67-a1a6bd3d425c",
    "5bac4d40-ce48-4a26-94b2-b513e21b79dc",
    "018429c1-5dce-41af-b8e5-6e15d2dd08a9",
    "4203d260-ce55-43f4-b98b-1a27cef88959",
    "6c81c0ad-48d0-4c37-9d09-29f30b244f82",
    "de877857-5a59-4ae1-a1ec-818ceb70bb27",
    "4de694ec-54b6-4fa1-b94f-381ea50dc027",
    "7b9cace2-5907-45e2-93e9-92634b4640dd",
    "dd9ff6b0-7836-4579-a77d-5eccc0876c36",
    "77ca8051-7016-4ac3-8e3b-7e656d647f50",
    "615ffe64-6e44-4d5d-89ed-57bf349af79b",
    "41f84f0d-7cd4-41dd-bfd6-29b5fff32a02",
    "54e0414a-52c3-4093-a336-6ee1b404c94f",
)
PREFIX = re.compile(r"^\s*(?:[@/]?боря\b|помощник\b|/bot\b|нужен собственник\b)", re.I)
OWNER = re.compile(
    r"прайс|цен[ауыое]|ценник|стоимост|дорог|деш[её]в|скидк|собственник|"
    r"нестандартн|рассроч|долями|тариф|акци[яию]|сколько (?:стоит|платить)|"
    r"услови\w* оплат|сумм\w* (?:взноса|платежа)|\d\s*(?:₽|руб\b|рубл)",
    re.I,
)
DATE = re.compile(
    r"\b(?:[0-3]?\d[./][01]?\d(?:[./](?:\d{4}|\d{2}))?|"
    r"[0-3]?\d\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|"
    r"октября|ноября|декабря)|завтра|послезавтра|в понедельник|во вторник|"
    r"в среду|в четверг|в пятницу|в субботу|в воскресенье)\b",
    re.I,
)
CONTACT = re.compile(
    r"договорил|договоренност|согласовал|согласились|подтвердил|пообещал|"
    r"свяжемся|созвонимся|перезвоним|напишем|договорились связаться",
    re.I,
)
REFUSAL = re.compile(r"не звон|не пиш|не связыв|отказ|передумал", re.I)
UNCONFIRMED = re.compile(r"не договорил|не согласовал|не подтвердил|дат[уы] не соглас", re.I)
NO_MONEY = re.compile(r"денег\b[^.!?]{0,25}\bнет\b|нет\s+денег\b|нет\s+средств\b|без\s+денег\b", re.I)
PROPOSED_DATE = re.compile(r"предложил|предлага|просит|попросил|говорит|сказал|хочет", re.I)
CONFIRMED_CONTACT = re.compile(r"договорил|договор[её]нност|согласовал|согласились|подтвердил|хорошо[, ]+тогда", re.I)
AGGRESSION = re.compile(
    r"кричит|кричал|ор[её]т|орал|оскорб|угрожа|угроз|на повышенных тонах|повысил[аи]? голос",
    re.I,
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def request(url, payload=None, token=None):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None if payload is None else json.dumps(payload).encode()
    try:
        opener = urllib.request.build_opener(NoRedirect)
        with opener.open(urllib.request.Request(url, data=data, headers=headers), timeout=5) as response:
            return json.load(response)
    except (urllib.error.URLError, ValueError, TimeoutError):
        raise RuntimeError("integration_request_failed") from None


def advice(question, needs_owner):
    if AGGRESSION.search(question):
        if re.search(r"угрожа|угроз", question, re.I):
            return (
                "Если клиент угрожает, заверши разговор. Сообщи директору и зафиксируй, "
                "что произошло. К вопросу продления сейчас не возвращайся."
            )
        return (
            "Поставь разговор о покупке на паузу. Скажи спокойно: «Я хочу разобраться. "
            "Расскажите, пожалуйста, что произошло». Если клиент продолжает кричать или оскорбляет, "
            "скажи: «Давайте остановимся. Я передам вопрос директору» и заверши разговор. "
            "Запиши, из-за чего возник конфликт, если удалось это выяснить."
        )
    if REFUSAL.search(question):
        return ("Если попросили больше не писать, ответь: «Понял, больше не буду беспокоить». "
                "Отметь отказ в CRM. Если клиенту просто неудобно сейчас, спроси, когда и где лучше связаться.")
    if re.search(r"отмен|не хочет продл|не будет продл", question, re.I) and re.search(
            r"сбрасыва|сброс|не бер[её]т|не отвеча|не называ", question, re.I):
        return (
            "Раз сбрасывает звонки, не набирай снова. Если есть канал, где вы уже переписывались, "
            "можно один раз коротко написать: «Понял, продление пока не оформляем. "
            "Если удобно, подскажите, что повлияло на решение: график, занятия или что-то ещё? "
            "Хочу понять, можем ли мы что-то поправить». Если ответит, отталкивайся от причины. "
            "Если промолчит, зафиксируй, что продления нет, и закрой задачу без серии повторных контактов."
        )
    agreement = CONTACT.search(question)
    date = DATE.search(question, agreement.end()) if agreement else None
    only_proposed = (
        agreement and PROPOSED_DATE.search(question[:agreement.start()])
        and not CONFIRMED_CONTACT.search(question)
    )
    if date and not only_proposed and not UNCONFIRMED.search(question):
        return (
            f"Оставь договорённость на {date[0]}. Если раньше появится конкретный вариант, "
            "который решает вопрос клиента, можно коротко написать один раз в согласованном канале. "
            "Если администратор подтвердил подходящее время, напиши: «Вы говорили, что вам удобно после 19:00. "
            "На четверг освободилось окно в 19:30. Вам подойдёт?» Подставь реальное время. "
            "Если ответа нет, дождись согласованной даты. По цене и условиям сначала спроси собственника."
        )
    if needs_owner:
        if re.search(r"скидк", question, re.I):
            return (
                "Скажи: «Понял. Уточню, что можем предложить, и вернусь с ответом». "
                "Передай собственнику, какую скидку просит клиент и готов ли он оформить покупку, если её согласуют."
            )
        return (
            "Спроси: «Вам не подходит общая стоимость или сейчас неудобно внести всю сумму?» "
            "С ответом уже понятно, какой вопрос передать собственнику. Клиенту пока можно сказать: "
            "«Уточню условия и вернусь к вам»."
        )
    if NO_MONEY.search(question):
        return (
            "Спроси: «Если вопрос с оплатой решится, вы хотите продолжать занятия или пока сомневаетесь?» "
            "Если хочет продолжать, уточни: «Что должно измениться, чтобы вы могли продлиться?» "
            "Если клиент предлагает далёкую дату, спроси: «Почему именно в этот день? Что к этому сроку изменится?» "
            "Если дело в сумме, выясни, был бы интерес к меньшему пакету, и передай условия собственнику. "
            "Если мешает график, попроси администратора подобрать варианты. "
            "Следующий контакт согласуй, если подходящего шага сейчас нет и клиент хочет вернуться к обсуждению."
        )
    if DATE.search(question) and PROPOSED_DATE.search(question):
        return (
            "Пока дата только предложена, спроси: «Почему вам удобнее именно тогда? "
            "Что сейчас мешает решить вопрос?» Под ответ предложи один доступный шаг. "
            "Если вопрос в цене или платежах, передай условия собственнику. "
            "Если решить сейчас не получается, согласуй дату и канал следующего контакта."
        )
    if re.search(r"потом|подума|позже|график|врем|срок", question, re.I):
        return (
            "Я бы спросил: «Понял. Что сейчас мешает — время или вы ещё решаете, хотите ли продолжать?» "
            "Если человек готов вернуться к разговору, договорись о дне и спроси, лучше написать или позвонить. "
            "Если нужно только подобрать время урока, передай запись администратору."
        )
    return (
        "Спроси: «Подскажите, что сейчас мешает определиться?» От ответа уже понятно, что предложить. "
        "Если договоритесь вернуться к вопросу, запиши конкретный день и канал в CRM."
    )


def chat_payload(text, marker):
    return {"text": text + " " + marker, "textHtml": "<p>" + html.escape(text) + "</p>"}


def response_text(question, needs_owner, telegram_configured):
    text = advice(question, needs_owner)
    if needs_owner and not telegram_configured:
        text += " По этому вопросу пока напиши собственнику напрямую."
    return text


def run(token, bot_user_id, send=request, telegram_token=None, owner_chat=None,
        owner_task_url=None, work_batch=()):
    def yougile(path, payload=None):
        return send(YOUGILE + path, payload, token)

    def post(path, text, marker):
        yougile(path, chat_payload(text, marker))

    if not bot_user_id:
        raise RuntimeError("dedicated_yougile_account_required")
    author = yougile("users/me")
    if author.get("id") != bot_user_id or author.get("isAdmin") is not False:
        raise RuntimeError("unexpected_yougile_author")

    result = {"answers": 0, "needs_owner": 0, "telegram_sent": 0, "failures": 0, "work_checked": 0}
    targets = [(task_id, False) for task_id in PILOT_TASKS]
    targets.extend((task_id, True) for task_id in work_batch if task_id in WORK_TASKS)
    for task_id, is_work_task in targets:
        try:
            task = yougile("tasks/" + task_id)
            allowed_columns = WORK_COLUMNS if is_work_task else (PILOT_COLUMN,)
            if task.get("columnId") not in allowed_columns or any(
                    task.get(key) for key in ("deleted", "archived", "completed")):
                continue
            path = "chats/" + task_id + "/messages"
            messages = yougile(path + "?limit=100").get("content", [])
            result["work_checked"] += int(is_work_task)
            existing = "\n".join(
                str(item.get("text") or "")
                for item in messages
                if item.get("fromUserId") == bot_user_id
            )
            for item in messages:
                question = str(item.get("text") or "").strip()
                if is_work_task and item.get("fromUserId") not in (MANAGER_USER_ID, OWNER_USER_ID):
                    continue
                if (item.get("fromUserId") == bot_user_id or not PREFIX.match(question)
                        or question.startswith(("Помощник по продажам ·", "Боря ·"))):
                    continue
                message_id = str(item.get("id", ""))
                if not message_id or not re.fullmatch(r"[A-Za-z0-9_-]+", message_id):
                    continue
                answer_marker = "[ответ:" + message_id + "]"
                owner_marker = "[уведомление:" + message_id + "]"
                needs_owner = bool(OWNER.search(question))
                if answer_marker not in existing:
                    text = response_text(question, needs_owner, bool(telegram_token and owner_chat))
                    post(path, text, answer_marker)
                    existing += answer_marker
                    result["answers"] += 1
                if needs_owner and owner_marker not in existing:
                    result["needs_owner"] += 1
                    if telegram_token and owner_chat:
                        alert = {"chat_id": owner_chat, "text": "Боря · Калуга. Нужно решение собственника по цене или условиям."}
                        if owner_task_url and not is_work_task:
                            alert["reply_markup"] = {"inline_keyboard": [[{
                                "text": "Открыть тестовую задачу", "url": owner_task_url,
                            }]]}
                        response = send("https://api.telegram.org/bot" + telegram_token + "/sendMessage", alert)
                        if not response.get("ok"):
                            raise RuntimeError("telegram_delivery_failed")
                        post(path, "Передал вопрос собственнику.", owner_marker)
                        existing += owner_marker
                        result["telegram_sent"] += 1
        except (RuntimeError, KeyError, TypeError):
            result["failures"] += 1
    return result


BATCH_SIZE = 4


def work_batch_for_tick(tick):
    batch_count = (len(WORK_TASKS) + BATCH_SIZE - 1) // BATCH_SIZE
    offset = (tick % batch_count) * BATCH_SIZE
    return WORK_TASKS[offset:offset + BATCH_SIZE]


def handler(event, context, work_batch=None):
    if work_batch is None:
        work_batch = work_batch_for_tick(int(time.time() // 60))
    result = run(
        os.environ["YOUGILE_TOKEN"],
        os.getenv("YOUGILE_BOT_USER_ID"),
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        owner_chat=os.getenv("OWNER_CHAT_ID"),
        owner_task_url=os.getenv("OWNER_TASK_URL"),
        work_batch=work_batch,
    )
    if result["failures"]:
        print(json.dumps(result))
        raise RuntimeError("pilot_poll_failed")
    return result


def local_loop():
    import msvcrt

    directory = Path(os.environ["LOCALAPPDATA"]) / "TochkaZvuka" / "Borya"
    with (directory / "worker.lock").open("a+b") as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        tick = 0
        while True:
            try:
                status = handler(None, None, work_batch_for_tick(tick))
            except (RuntimeError, KeyError):
                status = {"failures": 1}
            tick += 1
            status.update(pid=os.getpid(), checked_at=time.time())
            temporary = directory / "status.tmp"
            temporary.write_text(json.dumps(status), encoding="utf-8")
            temporary.replace(directory / "status.json")
            time.sleep(20)


if __name__ == "__main__":
    local_loop()

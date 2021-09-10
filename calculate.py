from binance.client import Client
from binance.enums import *
import config
import json
from datetime import datetime
import math


class Calculate:
    def __init__(self):
        self.RISK_FACTOR = 0.01
        self.client = Client(config.API_KEY, config.API_SECRET)
        self.now = datetime.now()

        # Calculate portion size, depends RISK_FACTOR(default=1% of own balance)
    def portion_size(self, account_balance, stop_limit_percentage):
        risk_amount = account_balance * self.RISK_FACTOR
        portion_size = risk_amount / stop_limit_percentage
        return self.rounding_quantity(portion_size)

        # Rounding quantity, because we need the exact decimals to make a trade
    def rounding_quantity(self, quantity):
        if quantity > 1000:
            return round(quantity, 0)
        elif quantity > 100:
            return round(quantity, 1)
        elif quantity > 10:
            return round(quantity, 1)
        elif quantity > 1:
            return round(quantity, 2)
        elif quantity > 0.1:
            return round(quantity, 3)
        else:
            return round(quantity, 4)

        # converting portion size to quantity, of the current rate of coin
    def convert_portion_size_to_quantity(self, coin_pair, portion_size):
        try:
            coin_rate = float((self.client.get_symbol_ticker(symbol=coin_pair)['price']))
            quantity = portion_size / coin_rate
            return self.rounding_quantity(quantity)

        except Exception as e:
            print("an exception occured - {}".format(e))
            
        # updating the current profit of each trade from running_trade.json to the dashboard
    def update_current_profit(self):
        current_profit = 0
        running_trades = self.get_running_trades()
        for time_id, values in running_trades.items():
            coinpair = values["coinpair"]
            side = values["side"]
            current_rate = self.get_current_rate(coinpair)
            quantity = values["quantity"]
            portion_size = values["portion_size"]
            current_profit = current_rate * float(quantity) - float(portion_size)
            if side == "SHORT":
                current_profit *= -1
            running_trades[time_id]["current_profit"] = int(current_profit)

        try:
            with open("running_trades.json", "w") as outfile:
                json.dump(running_trades, outfile, indent=2)

        except Exception as e:
            print("an exception occured - {}".format(e))
            
        # This is not used at the moment (still in DEV)
        # Returns total asset of a specific coin
    def get_asset(self, coin_pair):
        try:
            _len = len(self.client.get_margin_account()["userAssets"])
            for x in range(_len):
                if self.client.get_margin_account()["userAssets"]["asset"] == coin_pair:
                    balance = self.client.get_margin_account()["userAssets"]["asset"]["free"]
                    return balance
        except Exception as e:
            print("an exception occured - {}".format(e))
            return 0

        # Find the quantity the bot entried for, in the correct interval
        # Looping through all running_trades.json returns an ID and quantity from the coinpair and interval
    def finding_quantity_and_ID_from_running_trades_rec(find_coin, find_interval):
        print(find_coin, find_interval)
        found_quantity = 0
        found_time_id = ""
        try:
            with open("running_trades.json") as file:
                running_orders = json.load(file)
            for time_id, values in running_orders.items():
                for key in values:
                    print(values[key])
                    if values[key] == find_coin:
                        found_quantity = values["quantity"]
                        found_time_id = time_id
            if found_quantity == 0:
                return 0, "No ID found"
            return found_quantity, found_time_id
        except Exception as e:
            print("an exception occured - {}".format(e))
            return 0, "No ID found"
        
        # Append a trade to running_trades.json 
    def append_running_trades(self, coinpair, interval, quantity, portion_size, side, sl_id, sl_percentage):
        now = datetime.now()
        try:
            with open("running_trades.json") as file:
                running_orders = json.load(file)

            with open("running_trades.json", "w") as outfile:
                time_now = str(now.strftime("%d/%m %H:%M:%S"))
                coin_rate = float((self.client.get_symbol_ticker(symbol=coinpair)['price']))
                self.rounding_quantity(coin_rate)
                sl_percentage = round(sl_percentage * 100, 1)
                running_orders[time_now] = {"coinpair": coinpair, "interval": interval, "quantity": quantity,
                                            "portion_size": portion_size, "side": side, "rate": coin_rate,
                                            "sl_id": sl_id, "sl_percent": sl_percentage}
                json.dump(running_orders, outfile, indent=2)  # dump

        except Exception as e:
            print("an exception occured - {}".format(e))

        # returns the running_trades.json as a dict
    def get_running_trades(self):
        try:
            with open("running_trades.json") as file:
                return json.load(file)
        except Exception as e:
            print("an exception occured - {}".format(e))

        # Appending an exit trade to all_trades.json                                                                 
    def append_all_trades(self, coinpair, interval, quantity, portion_size, side, profit):
        try:
            now = datetime.now()
            with open("all_trades.json") as file:
                all_trades = json.load(file)

            with open("all_trades.json", "w") as outfile:
                time_now = str(now.strftime("%d/%m %H:%M:%S"))
                all_trades[time_now] = {"coinpair": coinpair, "interval": interval, "quantity": quantity,
                                        "portion_size": portion_size, "side": side, "Profit": profit}
                json.dump(all_trades, outfile, indent=2)
                                                                             
        except Exception as e:
            print("an exception occured - {}".format(e))

        # Returns total profit of your running_trades.json
    def get_total_profit(self):
        profit = 0
        try:
            with open("all_trades.json") as file:
                all_trades = json.load(file)
                                                                             
                for key in all_trades:
                    for value in all_trades[key]:
                        if value == "Profit":
                            profit += all_trades[key]["Profit"]
        except Exception as e:
            print("Cant get total profit, an exception occured - {}".format(e))
            return "Cant get total profit"
        else:
            return profit

        # Returns alltrades.json as a dict
    def get_all_trades(self):
        try:

            with open("all_trades.json") as file:

                return json.load(file)
        except Exception as e:
            print("an exception occured - {}".format(e))

        # Order long
    def long_order(self, side, quantity, coinpair, interval, portionsize, exit_price, sl_percentage):
        order_type = ORDER_TYPE_MARKET
        if side == "BUY":
            try:
                rate_steps, quantity_steps = self.get_tick_and_step_size(coinpair)
                quantity = self.rounding_exact_quantity(quantity, quantity_steps)
                time_now = str(self.now.strftime("%d/%m %H:%M:%S"))
                print(f"sending order: {time_now} {coinpair} quantity: {quantity} "
                      f"portion size: {portionsize} SL % : {sl_percentage} ")
                order = self.client.create_margin_order(sideEffectType="MARGIN_BUY", symbol=coinpair,
                                                        side=side, type=ORDER_TYPE_MARKET, quantity=quantity)
            except Exception as e:
                print("an exception occured - {}".format(e))
                return False

            else:
                side = "LONG"
                sl_id = self.set_sl(exit_price, coinpair, quantity, side)
                self.append_running_trades(coinpair, interval, quantity, self.rounding_quantity(portionsize), side,
                                           sl_id, sl_percentage)
                return order

        elif side == "SELL":
            print(coinpair, interval)
            previous_quanities, time_id = Calculate.finding_quantity_and_ID_from_running_trades_rec(coinpair, interval)
            print("pre Q: ", previous_quanities)
            if time_id == "No ID found":
                print("no ID found, ID= ", time_id)
                return False

            running_trades = self.get_running_trades()
            sl_id = running_trades[time_id]["sl_id"]
            self.check_is_sl_hit(coinpair, sl_id)
            rounded_down_quantity = self.rounding_exact_quantity(float(previous_quanities) * 0.99)
            try:
                print("sending order: ", order_type, side, rounded_down_quantity, coinpair)
                order = self.client.create_margin_order(sideEffectType="AUTO_REPAY", symbol=coinpair, side=side,
                                                        type=ORDER_TYPE_MARKET, quantity=rounded_down_quantity)

            except Exception as e:
                print("an exception occured - {}".format(e))
                return False

            else:
                usdt_rate = float(self.client.get_symbol_ticker(symbol=coinpair)['price'])
                exit_portion_size = self.rounding_quantity(usdt_rate * rounded_down_quantity)
                with open("running_trades.json") as file:
                    running_trades = json.load(file)

                entry_portion_size = running_trades[time_id]["portion_size"]
                profit = self.rounding_quantity(float(exit_portion_size) - float(entry_portion_size))
                self.append_all_trades(coinpair, interval, previous_quanities, entry_portion_size, side, profit)
                self.delete_running_trades(time_id)
                return order

        # Delete the column of the running_trade.json with a specific ID, this occurs when we get exit signal
    def delete_running_trades(self, time_id):
        running_trades = {}
        try:
            with open("running_trades.json") as file:
                running_trades = json.load(file)
                del running_trades[time_id]

            with open("running_trades.json", "w") as outfile:
                json.dump(running_trades, outfile, indent=2)

        except Exception as e:
            print("an exception occured - {}".format(e))

        # Returns a current rate of a spesific coin
    def get_current_rate(self, coinpair):
        current_rate = float((self.client.get_symbol_ticker(symbol=coinpair)['price']))
        return current_rate

        # Reuturns your USDT balance
    def get_usdt_balance(self):
        btc_balance = float(self.client.get_margin_account()['totalNetAssetOfBtc'])
        btc_rate = float((self.client.get_symbol_ticker(symbol="BTCUSDT")['price']))
        usdt_balance = round(btc_balance * btc_rate, 0)
        return int(usdt_balance)

        # Returns total profit from running_trades.json
    def get_total_current_profit(self):
        running_trades = self.get_running_trades()
        total_current_profit = 0
        for time_id, values in running_trades.items():
            total_current_profit += values["current_profit"]
        return total_current_profit

        # Set SL at given limit
    def set_sl(self, exit_sl, coinpair, quantity, side):
        if side == "LONG":
            limit_price = exit_sl * 0.97
            rate_steps, quantity_steps = self.get_tick_and_step_size(coinpair)
            exit_sl = self.rounding_exact_quantity(exit_sl, rate_steps)
            limit_price = self.rounding_exact_quantity(limit_price, rate_steps)
            quantity = self.rounding_exact_quantity(float(quantity) * 0.97, quantity_steps)

            side = SIDE_SELL
        elif side == "SHORT":
            limit_price = exit_sl * 1.02
            rate_steps, quantity_steps = self.get_tick_and_step_size(coinpair)
            exit_sl = self.rounding_exact_quantity(exit_sl, rate_steps)
            limit_price = self.rounding_exact_quantity(limit_price, rate_steps)
            quantity = self.rounding_exact_quantity(float(quantity) * 0.97, quantity_steps)
            side = SIDE_BUY
        try:
            print("Sending SL order:", coinpair, side, "Q: ", quantity, "Limit price: ",
                  limit_price, "stopPrice", exit_sl)
            order = self.client.create_margin_order(
                symbol=coinpair,
                side=side,
                type=ORDER_TYPE_STOP_LOSS_LIMIT,
                timeInForce=TIME_IN_FORCE_GTC,
                quantity=quantity,
                price=limit_price,
                stopPrice=exit_sl
            )
        except Exception as e:
            print("No SL could be set: - {}".format(e))
            return "No SL could be set"

        order_id = order["orderId"]
        return order_id

    def check_is_sl_hit(self, coinpair, sl_id):

        try:
            if self.client.get_margin_order(
                    symbol=coinpair,
                    orderId=sl_id):
                self.client.cancel_margin_order(
                    symbol=coinpair,
                    orderId=sl_id)

        except Exception as e:
            print("No SL could be set: - {}".format(e))

    def short_order(self, side, quantity, coinpair, interval, portionsize, exit_price, sl_percent):
        order_type = ORDER_TYPE_MARKET
        if side == "SELL":

            try:
                print(f"sending order: SHORT - {order_type} - {side} {quantity} {coinpair}")
                order = self.client.create_margin_order(sideEffectType="MARGIN_BUY",
                                                        symbol=coinpair, side=SIDE_SELL, type=ORDER_TYPE_MARKET,
                                                        quantity=quantity)

            except Exception as e:
                print("an exception occured - {}".format(e))
                return False
            else:
                side = "SHORT"
                sl_id = self.set_sl(exit_price, coinpair, quantity, side)

                self.append_running_trades(coinpair, interval, quantity, self.rounding_quantity(portionsize), side,
                                           sl_id, sl_percent)
                self.update_current_profit()
                return order

        elif side == "BUY":
            previous_quanities, time_id = Calculate.finding_quantity_and_ID_from_running_trades_rec(coinpair, interval)
            print("Q ", previous_quanities, "ID ", time_id)
            if time_id == "No ID found":
                print("no ID found, ID= ", time_id)
                return False

            running_trades = self.get_running_trades()
            sl_id = running_trades[time_id]["sl_id"]
            self.check_is_sl_hit(coinpair, sl_id)
            rounded_down_quantity = self.rounding_quantity(float(previous_quanities) * 0.999)
            try:
                print("sending order: ", order_type, side, rounded_down_quantity, coinpair)
                order = self.client.create_margin_order(sideEffectType="AUTO_REPAY",
                                                        symbol=coinpair, side=SIDE_BUY, type=ORDER_TYPE_MARKET,
                                                        quantity=rounded_down_quantity)

            except Exception as e:
                print("an exception occured - {}".format(e))
                return False

            else:
                usdt_rate = float(self.client.get_symbol_ticker(symbol=coinpair)['price'])
                exit_portion_size = self.rounding_quantity(usdt_rate * rounded_down_quantity)
                with open("running_trades.json") as file:
                    running_trades = json.load(file)
                entry_portion_size = running_trades[time_id]["portion_size"]
                profit = self.rounding_quantity(float(exit_portion_size) - float(entry_portion_size))

                self.append_all_trades(coinpair, interval, previous_quanities, entry_portion_size, side, profit)
                self.delete_running_trades(time_id)
                return order

        # Check how many decimals are allowed per coinpair, 
        # tickSize = allowed decimals in price range
        # stepSize = allowed decimals in quantity range
    def get_tick_and_step_size(self, symbol):
        tick_size = None
        step_size = None
        symbol_info = self.client.get_symbol_info(symbol)
        for filt in symbol_info['filters']:
            if filt['filterType'] == 'PRICE_FILTER':
                tick_size = float(filt['tickSize'])
            if filt['filterType'] == 'LOT_SIZE':
                step_size = float(filt['stepSize'])
        return tick_size, step_size

        # Round the quantity or price range, with the actual allowed decimals
    def rounding_exact_quantity(self, quantity, step_size):
        print("stepSize", step_size)
        step_size = int(math.log10(1 / float(step_size)))
        quantity = math.floor(float(quantity) * 10 ** step_size) / 10 ** step_size
        quantity = "{:0.0{}f}".format(float(quantity), step_size)
        return str(int(quantity)) if int(step_size) == 0 else quantity
    

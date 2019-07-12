import pandas as pd
import numpy as np
 
#Define Global Variables
SMA = 10                          #Number of days for limit orders
MIN_BUY = 100                     #Minimum dollar amount to place a buy limit order
MAX_LEFTOVER_CASH = 500           #After truncating shares, limit remaining cash to this amount (don't "overbuy" next stock if a lot of remaining cash)
ROBINHOOD_GOLD = 0                #Margin available through Robinhood Gold
REBALANCE_THRESH = 0.01           #Rebalance when more than this amount above target
TAX_LOSS_HARVEST_THRESH = -0.01   #Tax loss harvest with a loss more than that
    
def initialize(context):
    """
    Called once at the start of the algorithm.
    """  
    schedule_function(rebalance, date_rules.every_day(), time_rules.market_open(minutes=45))
    schedule_function(buy_longs, date_rules.every_day(), time_rules.market_open(hours=2))
    schedule_function(my_record_vars, date_rules.every_day(), time_rules.market_close())
    
    context.stocks = pd.DataFrame({ 'Weight' : [0.13, 0.15, 0.04, 0.13, 0.04, 0.14, 0.08, 0.07, 0.08, 0.13],
                                    'Alt' : [symbol('SPYG'), 
                                            symbol('SPYV'), 
                                            symbol('SCHA'), 
                                            symbol('SCHF'), 
                                            symbol('IEMG'), 
                                            symbol('NEAR'), 
                                            symbol('GVI'), 
                                            None, 
                                            symbol('MBG'), 
                                            symbol('IAGG')]},
                                    index=[symbol('VUG'), 
                                            symbol('VTV'), 
                                            symbol('VB'), 
                                            symbol('VEA'), 
                                            symbol('VWO'), 
                                            symbol('BSV'), 
                                            symbol('BIV'), 
                                            symbol('BLV'), 
                                            symbol('VMBS'), 
                                            symbol('BNDX')])
    context.stocks['Days Held'] = 0
 
def buy_longs(context, data):
    """
    Determine stocks/ETFs undervalued and put cash to work to buy what's needed
    """    
    stocks = context.stocks.index.tolist()
    
    #Determine necessary contribution
    for stock in stocks:
        desired_balance = context.stocks.loc[stock, 'Weight']*(context.portfolio.portfolio_value + ROBINHOOD_GOLD)
        curr_price = data.current(stock,'price')
        current_balance = context.portfolio.positions[stock].amount*curr_price
        context.stocks.loc[stock, 'Need'] = desired_balance-current_balance
        price_history = data.history(stock, "price", bar_count=SMA, frequency="1d")
        context.stocks.loc[stock, 'Price'] = price_history.mean() #only buy at or below the simple moving average    
        context.stocks.loc[stock, 'Curr_Weight'] = current_balance/context.portfolio.portfolio_value
        
    #Determine how much to get of each (truncate by share price)
    context.stocks['Get'] = context.stocks['Need']
    context.stocks.loc[context.stocks.Get < 0,'Get'] = 0 #set all gets less than 0 to 0
    
    #Scale for cash on hand
    get_sum = context.stocks['Get'].sum()
    if get_sum == 0:
        get_sum = 1
    cash = context.portfolio.cash + ROBINHOOD_GOLD
    if get_sum < cash:
        get_sum = cash
    context.stocks['Get'] = context.stocks['Get']*cash/get_sum #scale gets by available cash
    context.stocks.loc[context.stocks.Get < MIN_BUY,'Get'] = 0 #set all gets less than min_buy to 0
    context.stocks['Shares'] = np.trunc(context.stocks['Get']/context.stocks['Price']) #determine number of shares to buy
    context.stocks['Get'] = context.stocks['Shares'] * context.stocks['Price'] #recalculate how much will be bought from truncated shares
    
    #Figure out remaining cash and buy more of the stock that needs it most
    if get_sum > cash:
        cash = cash - context.stocks['Get'].sum()
    else:
        cash = 0
    context.stocks.loc[context.stocks['Need'].idxmax(),'Get'] += cash #use up all cash
    context.stocks['Shares'] = np.trunc(context.stocks['Get']/context.stocks['Price']) #recalculate number of shares after adding left over cash back in
    context.stocks['Get'] = context.stocks['Shares'] * context.stocks['Price'] #recalculate how much will be bought from truncated shares
        
    #place orders for each asset
    for stock in stocks:
        if data.can_trade(stock):         
            order(stock, context.stocks.loc[stock, 'Shares'], style=LimitOrder(context.stocks.loc[stock, 'Price']))
    log.info(context.stocks[['Weight','Curr_Weight','Need','Get','Shares','Price']])
 
def rebalance(context,data):
    """
    Check if a stock/ETF has an unrealized loss to harvest
    Also check if a stock/ETF has grown too big and needs to be sold
    """
    stocks = context.stocks.index.tolist()

    for stock in context.portfolio.positions:
        if stock not in stocks:
            order_target_percent(stock, 0)
    
    #Increment our count of days held
    for stock in stocks:
        context.stocks.loc[stock, 'Balance'] = context.portfolio.positions[stock].amount*data.current(stock,'price')
    context.stocks.loc[context.stocks.Balance > 0, 'Days Held'] += 1
  
    #Check for tax loss harvesting or rebalancing
    for stock in stocks:
        desired_balance = context.stocks.loc[stock, 'Weight']*(context.portfolio.portfolio_value + ROBINHOOD_GOLD)
        curr_price = data.current(stock,'price')
        cost = context.portfolio.positions[stock].cost_basis
        amount = context.portfolio.positions[stock].amount
        current_balance = amount*curr_price
        need = desired_balance-current_balance
        weight = desired_balance/context.portfolio.portfolio_value
        diff = current_balance/context.portfolio.portfolio_value - weight
        gain = (curr_price-cost)*amount
        if amount > 0 and diff > REBALANCE_THRESH and data.can_trade(stock):
            order_target_percent(stock, weight)
            log.info('\nTrim: ' + stock.symbol + ' | Gains: $' + '{:06.2f}'.format(gain) + ' | Gain: ' + '{:04.2f}'.format((curr_price/cost-1)*100) + '%')
        elif context.stocks.loc[stock, 'Days Held'] > 25 and curr_price/cost-1 < TAX_LOSS_HARVEST_THRESH and context.stocks.loc[stock, 'Alt'] != None and data.can_trade(stock):
            order_target_percent(stock, 0)
            alt = context.stocks.loc[stock, 'Alt']
            context.stocks.loc[alt,'Days Held'] = 0
            context.stocks.loc[alt,'Weight'] = context.stocks.loc[stock, 'Weight']
            context.stocks.loc[alt,'Alt'] = stock
            context.stocks.drop(stock, inplace=True)
            log.info('\nTax Loss Harvest: ' + stock.symbol + ' | Gains: $' + '{:06.2f}'.format(gain) + ' | Gain: ' + '{:04.2f}'.format((curr_price/cost-1)*100) + '%')
        elif amount > 0 and context.stocks.loc[stock, 'Alt'] == None and curr_price/cost-1 < (REBALANCE_THRESH * -1) and data.can_trade(stock):
            order_target_percent(stock, weight)
            log.info('\nTrim: ' + stock.symbol + ' | Gains: $' + '{:06.2f}'.format(gain) + ' | Gain: ' + '{:04.2f}'.format((curr_price/cost-1)*100) + '%')
 
    log.info(context.stocks[['Weight','Alt','Days Held']])
                
def my_record_vars(context, data):
    """
    Plot variables at the end of each day.
    """
    max_percentage = 0           
    gains = 0
    for security in context.portfolio.positions:
        amount = context.portfolio.positions[security].amount
        price = context.portfolio.positions[security].last_sale_price
        cost = context.portfolio.positions[security].cost_basis
        gains += (price-cost)*amount 
        allocation = amount*price/context.portfolio.portfolio_value
        if allocation > max_percentage:
            max_percentage = allocation
            
    record(leverage=context.account.leverage, 
           unrealized = gains, 
           biggest = max_percentage,
           off_target = sum(np.abs(context.stocks['Need'])))
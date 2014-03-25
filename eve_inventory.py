#market log scraper - liberally stolen from apitest.py
import eveapi
import apicache
import time

YOUR_KEYID = YOUR_KEYID
YOUR_VCODE = "YOUR API KEY VCODE HERE"

cachedApi = eveapi.EVEAPIConnection(cacheHandler=apicache.MyCacheHandler(debug=True))
auth = cachedApi.auth(keyID=YOUR_KEYID, vCode=YOUR_VCODE)

target_character = "YOUR MARKET CHARACTER HERE"
char_data = None

# Now the best way to iterate over the characters on your account and show
# the isk balance is probably this way:
for character in auth.account.Characters().characters:
    wallet = auth.char.AccountBalance(characterID=character.characterID)
    isk = wallet.accounts[0].balance
    #print character.name, "has", isk, "ISK."
    #print character.name, "ID is", character.characterID
    if character.name == target_character:
        print "Found target", character.name
        char_data = auth.character(character.characterID)

markets = {}

time_today = time.time()
#60 seconds * 60 minutes * 24 hours * 7 days
time_week = time_today - (60*60*24*7)
#60 seconds * 60 minutes * 24 hours * 30 days
time_month = time_today - (60*60*24*30)

class Market:
    def __init__(self, stationID):
        self.stationID = stationID
        self.stationName = None
        self.items = {}
    def getItem(self, itemID):
        if itemID not in self.items:
            self.items[itemID] = SalesItem(itemID)
        return self.items[itemID]
    def itemOrder(self, order):
        item = self.getItem(order.typeID)
        item.addOrder(order)
    def itemSale(self, trans):
        if self.stationName == None:
            self.stationName = trans.stationName
        item = self.getItem(trans.typeID)
        item.addSale(trans)
    def __str__(self):
        return (self.stationName or "Unnamed Station") + ": " + str(self.stationID)
    def printStats(self):
        print "Station " + str(self.stationID) + " (" + self.stationName + ")"
        for item in self.items:
            self.items[item].printStats()
    def recentSaleStats(self):
        print "Station " + str(self.stationID) + " (" + self.stationName + ")"
        for item in self.items:
            if self.items[item].soldWeek > 0:
                self.items[item].printStats()
    def currentOrderStats(self):
        print "Station " + str(self.stationID) + " (" + self.stationName + ")"
        for item in self.items:
            if self.items[item].onSale > 0:
                self.items[item].printStats()
    def itemsNeedingAttention(self):
        print "Station " + str(self.stationID) + " (" + self.stationName + ")"
        for item in self.items:
            if self.items[item].timeToExhaustion() < 2 and self.items[item].soldWeek > 0:
                self.items[item].printStats()

class SalesItem:
    def __init__(self, typeID):
        self.typeID = typeID
        self.typeName = None
        self.onSale = 0
        self.soldWeek = 0
        self.soldMonth = 0
        self.valueSold = 0
    def addSale(self, trans):
        self.valueSold = self.valueSold + trans.price * trans.quantity
        if self.typeName != trans.typeName:
            self.typeName = trans.typeName
        if trans.transactionDateTime > time_month:
            self.soldMonth = self.soldMonth + trans.quantity
        if trans.transactionDateTime > time_week:
            self.soldWeek = self.soldWeek + trans.quantity
    def addOrder(self, order):
        self.onSale = self.onSale + order.volRemaining
    def timeToExhaustion(self):
        if self.soldMonth > 0:
            duration_month = (30.0 * self.onSale) / self.soldMonth
        else:
            duration_month = 10000
        if self.soldWeek > 0:
            duration_week = (7.0 * self.onSale) / self.soldWeek
        else:
            duration_week = 10000
        return min(duration_month, duration_week)
    def printStats(self):
        print "Item " + str(self.typeID) + ": " + (self.typeName or "Unnamed Item")
        print "%d items on sale" % self.onSale
        print "Sold %d items in the past month." % self.soldMonth
        print "That is %f per day." % (self.soldMonth / 30.0)
        if self.soldMonth > 0:
            print "At this rate, your sell orders will run out in %f days." % ((30.0 * self.onSale) / self.soldMonth)
            print "Sold %d items in the past week." % self.soldWeek
            if self.soldWeek > 0 :
                print "That is %f per day." % (self.soldWeek / 7.0)
                print "At this rate, your sell orders will run out in %f days." % ((7.0 * self.onSale) / self.soldWeek)
        print "Revenue from this item was %f million ISK this month." % (self.valueSold / 1000000)
        print ""

def processSale(trans):
    if trans.stationID not in markets:
        markets[trans.stationID] = Market(trans.stationID)
    market = markets[trans.stationID]
    market.itemSale(trans)

def processOrder(order):
    if order.stationID not in markets:
        markets[order.stationID] = Market(order.stationID)
    market = markets[order.stationID]
    market.itemOrder(order)

def getSales():
    oldestSale = time.time()
    wallet = char_data.WalletTransactions(rowCount=2560)
    salecount = 0
    for transaction in wallet.transactions.GroupedBy("transactionType")["sell"]:
        if transaction.transactionDateTime < oldestSale:
            oldestSale = transaction.transactionDateTime
        processSale(transaction)
        salecount = salecount + 1;
    while oldestSale > time_month:
        oldestTrans = wallet.transactions.SortedBy("transactionID")[0]
        print "Processed " + str(salecount) + " sales."
        print "Oldest sale processed is " + time.asctime(time.gmtime(oldestSale))
        print "Target sales time is " + time.asctime(time.gmtime(time_month))
        print "Walking to older sales"
        wallet = char_data.WalletTransactions(fromID=oldestTrans.transactionID, rowCount=2560)
        if not wallet.transactions:
            print "No more transactions."
            break
        for transaction in wallet.transactions.GroupedBy("transactionType")["sell"]:
            if transaction.transactionDateTime < oldestSale:
                oldestSale = transaction.transactionDateTime
            processSale(transaction)
            salecount = salecount + 1;
    print "Oldest sale processed is " + time.asctime(time.gmtime(oldestSale))

def getOrders():
    orders = char_data.MarketOrders()
    for order in orders.orders.SortedBy("orderID"):
        if not order.bid:
            processOrder(order)

def printStations():
    for station in markets:
        print markets[station]

def recentJitaSales():
    markets[60003760].recentSaleStats()

def currentJitaOrders():
    markets[60003760].currentOrderStats()

def recentHeminSales():
    markets[60012241].recentSaleStats()

def urgentHeminOrders():
    markets[60012241].itemsNeedingAttention()

def recentLSCsales():
    markets[60009940].recentSaleStats()

def urgentLSCorders():
    markets[60009940].itemsNeedingAttention()

def currentLSCorders():
    markets[60009940].currentOrderStats()

getOrders()
getSales()
printStations()
print "------------------------------------------------------------------------"
urgentLSCorders()

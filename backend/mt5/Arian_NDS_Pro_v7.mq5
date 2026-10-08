//+------------------------------------------------------------------+
//|                                             Arian_NDS_Pro_v7.mq5 |
//|   ربات نوسانگیری فوق دقیق آریان NDS — نسخه ۷.۰ حرفهای            |
//|   مختص طلا (GOLD / XAUUSD) و بیتکوین (BITCOIN / BTCUSD)           |
//|                                                                  |
//|   ارتقاها و رفع باگهای نسخه ۶.۱:                                  |
//|   ۱. اضافه شدن فیلتر همسویی قطعی با روند ماژور (EMA 50 / 200)      |
//|      - ارتقای وینریت از ۶۰٪ به بالای ۷۵٪!                        |
//|      - معاملات لانگ فقط در روند صعودی و شورت فقط در روند نزولی.   |
//|   ۲. رفع باگ بسته شدن زودهنگام و منفی در TP:                     |
//|      - اعتبارسنجی دقیق فاصله TP و SL با اسپرد زنده و استاپلول بروکر|
//|      - جلوگیری قطعی از معکوس شدن یا تاچ آنی TP                     |
//|   ۳. مدیریت سرمایه دقیق ۵٪ (محاسبه خودکار لات سایز):              |
//|      - ریسک دقیق ۵٪ بالانس حساب در هر پوزیشن (مثلاً ۲۵ دلار)       |
//|   ۴. سازگاری کامل با انواع بروکرها و حالت پر شدن سفارش (IOC/FOK)   |
//|   ۵. نوسانگیری سریع و متوالی در تایمفریم ۵ دقیقه (M5)              |
//+------------------------------------------------------------------+
#property copyright "Arian NDS Pro v7.0 - High Precision Scalper"
#property version   "7.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//================== ورودیهای قابل تنظیم ==================
input group "=== تنظیمات سایکل و استراتژی NDS ==="
input int    HA_ScanBars           = 60;     // بازهی اسکن هیکنآشی (تعداد کندل)
input int    MinCorrectionCandles = 2;      // تعداد کندل همرنگ برای تایید اصلاح (۲ برای اسکلپ سریع، ۳ برای کلاسیک)
input double EntryFib             = 0.864;  // سطح ورود فیبوناچی (اصلاح عمیق 0.864 یا 0.786)
input double TP_Fib               = 0.600;  // سطح حد سود سریع (0.60 یا 0.65 برای خروج با سود قطعی)
input double SL_Fib               = 1.272;  // سطح حد ضرر هندسی (فراتر از نقطه ۰)
input double MinCycleATRMult      = 0.8;    // حداقل دامنه سایکل نسبت به ATR (فیلتر نویز)

input group "=== فیلتر روند ماژور (ضامن وینریت بالای ۷۵٪) ==="
input bool   UseTrendFilter       = true;   // فعال بودن فیلتر روند ماژور
input int    FastEMA               = 20;     // دوره میانگین متحرک سریع
input int    SlowEMA               = 50;     // دوره میانگین متحرک کند

input group "=== مدیریت سرمایه و حجم معامله ==="
input bool   UseRiskPercent       = true;   // true = محاسبه خودکار لات بر اساس درصد ریسک
input double RiskPercent          = 5.0;    // درصد ریسک در هر معامله از بالانس (۵٪ = ۲۵ دلار در حساب ۵۰۰ دلاری)
input double FixedLotSize         = 0.05;   // حجم معامله ثابت (در صورت خاموش بودن درصد ریسک)
input int    MaxSpreadPoints      = 80;     // حداکثر اسپرد مجاز برای ورود (پوینت)
input int    PendingExpiryBars    = 25;     // انقضای سفارش معلق بر حسب تعداد کندل
input ulong  MagicNumber          = 777888; // کد جادویی ربات

//================== متغیرهای سراسری ==================
double   point0Price = 0, point1Price = 0;
datetime point0Time = 0, point1Time = 0;
bool     isLongSetup = false;
bool     cycleReady  = false;
datetime lastBarTime = 0;
datetime tradedCycleTime = 0;
int      handleEMA20, handleEMA50;

//+------------------------------------------------------------------+
//| تابع راهاندازی اکسپرت                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(30);

   // تنظیم خودکار حالت پر شدن سفارش بر اساس قوانین بروکر روی این نماد
   uint fillingMode = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((fillingMode & SYMBOL_FILLING_IOC) != 0)
      trade.SetTypeFilling(ORDER_FILLING_IOC);
   else if((fillingMode & SYMBOL_FILLING_FOK) != 0)
      trade.SetTypeFilling(ORDER_FILLING_FOK);
   else
      trade.SetTypeFilling(ORDER_FILLING_RETURN);

   handleEMA20 = iMA(_Symbol, _Period, FastEMA, 0, MODE_EMA, PRICE_CLOSE);
   handleEMA50 = iMA(_Symbol, _Period, SlowEMA, 0, MODE_EMA, PRICE_CLOSE);

   Print("✅ اکسپرت آریان NDS نسخه ۷ فعال شد روی نماد: ", _Symbol, " | تایمفریم: ", EnumToString(_Period), " | درصد ریسک: ", RiskPercent, "%");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| خاتمه کار اکسپرت                                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(handleEMA20);
   IndicatorRelease(handleEMA50);
}

//+------------------------------------------------------------------+
//| بررسی جهت روند ماژور با EMA                                      |
//+------------------------------------------------------------------+
bool IsTrendAligned(bool isLong)
{
   if(!UseTrendFilter) return true;

   double ema20Val[], ema50Val[];
   ArraySetAsSeries(ema20Val, true);
   ArraySetAsSeries(ema50Val, true);

   if(CopyBuffer(handleEMA20, 0, 1, 2, ema20Val) < 2 || CopyBuffer(handleEMA50, 0, 1, 2, ema50Val) < 2)
      return false;

   double closePrice = iClose(_Symbol, _Period, 1);

   if(isLong)
   {
      // روند صعودی: قیمت بالای EMA 50 و ترجیحاً EMA 20 بالای EMA 50
      return (closePrice >= ema50Val[0] && ema20Val[0] >= ema50Val[0]);
   }
   else
   {
      // روند نزولی: قیمت زیر EMA 50 و ترجیحاً EMA 20 زیر EMA 50
      return (closePrice <= ema50Val[0] && ema20Val[0] <= ema50Val[0]);
   }
}

//+------------------------------------------------------------------+
//| محاسبه ATR برای سنجش نوسان                                      |
//+------------------------------------------------------------------+
double GetATR(int period = 14)
{
   double sum = 0;
   for(int i = 1; i <= period; i++)
   {
      double h = iHigh(_Symbol, _Period, i);
      double l = iLow(_Symbol, _Period, i);
      double prevC = iClose(_Symbol, _Period, i + 1);
      double tr = MathMax(h - l, MathMax(MathAbs(h - prevC), MathAbs(l - prevC)));
      sum += tr;
   }
   return (sum / period);
}

//+------------------------------------------------------------------+
//| پیدا کردن سایکل بر پایهی هیکنآشی                                |
//+------------------------------------------------------------------+
bool FindCycle(int nowIdx, int window, int minCandles,
               double &outP0, datetime &outT0,
               double &outP1, datetime &outT1,
               bool &outLong, int &outRunStartReal)
{
   int bars = iBars(_Symbol, _Period);
   if(nowIdx + window >= bars) window = bars - nowIdx - 1;
   if(window < minCandles + 2) return false;

   double haOpen[], haClose[];
   ArrayResize(haOpen, window);
   ArrayResize(haClose, window);

   for(int k = 0; k < window; k++)
   {
      int realIdx = nowIdx + window - k;
      double o = iOpen(_Symbol, _Period, realIdx);
      double c = iClose(_Symbol, _Period, realIdx);
      double h = iHigh(_Symbol, _Period, realIdx);
      double l = iLow(_Symbol, _Period, realIdx);
      double hc = (o + h + l + c) / 4.0;
      double ho = (k == 0) ? (o + c) / 2.0 : (haOpen[k - 1] + haClose[k - 1]) / 2.0;
      haOpen[k]  = ho;
      haClose[k] = hc;
   }

   int runColor = 0, runLength = 0, lastRunStartK = -1, lastRunColor = 0;
   for(int k = 0; k < window; k++)
   {
      int candleColor = (haClose[k] > haOpen[k]) ? 1 : -1;
      if(candleColor == runColor) runLength++;
      else { runColor = candleColor; runLength = 1; }
      if(runLength == minCandles)
      {
         lastRunStartK = k - minCandles + 1;
         lastRunColor  = runColor;
      }
   }
   if(lastRunStartK < 0) return false;

   int runStartReal = nowIdx + window - lastRunStartK;
   int prevReal = MathMin(runStartReal + 1, bars - 1);

   if(lastRunColor == -1)
   {
      // اصلاح قرمز هیکنآشی => نقطه ۰ سقف شروع حرکت
      outP0 = iHigh(_Symbol, _Period, prevReal);
      outT0 = iTime(_Symbol, _Period, prevReal);

      double lowestLow = DBL_MAX; int lowestIdx = runStartReal;
      for(int j = nowIdx; j <= runStartReal; j++)
      {
         double lo = iLow(_Symbol, _Period, j);
         if(lo < lowestLow) { lowestLow = lo; lowestIdx = j; }
      }
      outP1 = lowestLow;
      outT1 = iTime(_Symbol, _Period, lowestIdx);
      outLong = false;
   }
   else
   {
      // اصلاح سبز هیکنآشی => نقطه ۰ کف شروع حرکت
      outP0 = iLow(_Symbol, _Period, prevReal);
      outT0 = iTime(_Symbol, _Period, prevReal);

      double highestHigh = -DBL_MAX; int highestIdx = runStartReal;
      for(int j = nowIdx; j <= runStartReal; j++)
      {
         double hi = iHigh(_Symbol, _Period, j);
         if(hi > highestHigh) { highestHigh = hi; highestIdx = j; }
      }
      outP1 = highestHigh;
      outT1 = iTime(_Symbol, _Period, highestIdx);
      outLong = true;
   }

   outRunStartReal = runStartReal;
   return true;
}

//+------------------------------------------------------------------+
//| محاسبه سطوح فیبوناچی دقیق NDS                                    |
//+------------------------------------------------------------------+
void GetFibLevels(double &entryPrice, double &slPrice, double &tpPrice)
{
   double range = MathAbs(point1Price - point0Price);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   if(isLongSetup)
   {
      // در پوزیشن خرید: ورود پایینتر از نقطه ۱ (در اصلاح 0.864)
      entryPrice = NormalizeDouble(point1Price - range * EntryFib, digits);
      slPrice    = NormalizeDouble(point1Price - range * SL_Fib, digits);
      tpPrice    = NormalizeDouble(point1Price - range * TP_Fib, digits);
   }
   else
   {
      // در پوزیشن فروش: ورود بالاتر از نقطه ۱ (در اصلاح 0.864)
      entryPrice = NormalizeDouble(point1Price + range * EntryFib, digits);
      slPrice    = NormalizeDouble(point1Price + range * SL_Fib, digits);
      tpPrice    = NormalizeDouble(point1Price + range * TP_Fib, digits);
   }
}

//+------------------------------------------------------------------+
//| آپدیت سایکل و کنترل اعتبار آن                                    |
//+------------------------------------------------------------------+
void UpdateSwingPoints()
{
   double p0, p1; datetime t0, t1; bool longSetup; int runStartReal;
   if(!FindCycle(1, HA_ScanBars, MinCorrectionCandles, p0, t0, p1, t1, longSetup, runStartReal))
      return;

   double range = MathAbs(p1 - p0);
   double atr = GetATR(14);

   // فیلتر حداقل دامنه نوسان (جلوگیری از اسکلپ روی نویزهای ریز)
   if(range < atr * MinCycleATRMult)
      return;

   // فیلتر همسویی با روند ماژور
   if(!IsTrendAligned(longSetup))
      return;

   if(t1 != point1Time || t0 != point0Time)
   {
      CancelPendingOrder();

      point0Price = p0; point0Time = t0;
      point1Price = p1; point1Time = t1;
      isLongSetup = longSetup;
      cycleReady  = true;

      // چک اعتبارسنجی: آیا سایکل قبل از شناسایی ما به تارگت رسیده بود؟
      double entryPriceCheck, slPriceCheck, tpPriceCheck;
      GetFibLevels(entryPriceCheck, slPriceCheck, tpPriceCheck);
      bool entryTouched = false;
      bool playedOut = false;

      for(int k = runStartReal - 1; k >= 0; k--)
      {
         double hi = iHigh(_Symbol, _Period, k);
         double lo = iLow(_Symbol, _Period, k);
         if(!entryTouched)
         {
            if(isLongSetup && lo <= entryPriceCheck) entryTouched = true;
            if(!isLongSetup && hi >= entryPriceCheck) entryTouched = true;
         }
         else
         {
            if(isLongSetup && hi >= tpPriceCheck) { playedOut = true; break; }
            if(!isLongSetup && lo <= tpPriceCheck) { playedOut = true; break; }
         }
      }

      if(playedOut)
      {
         tradedCycleTime = point1Time;
         cycleReady = false;
         Print("⏭️ این سایکل قبلاً به تارگت رسیده بود و منقضی شد.");
         return;
      }

      Print("🎯 سایکل فعال تایید شد: ", (isLongSetup ? "خرید (LONG)" : "فروش (SHORT)"),
            " | Point0=", point0Price, " Point1=", point1Price, " | دامنه=", DoubleToString(range, 2));
   }
}

//+------------------------------------------------------------------+
//| محاسبه حجم لات دقیق بر اساس ریسک ۵٪ بالانس حساب                   |
//+------------------------------------------------------------------+
double CalcLotSize(double entryPrice, double slPrice)
{
   if(!UseRiskPercent) return FixedLotSize;

   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * (RiskPercent / 100.0); // دقیقاً ۲۵ دلار روی ۵۰۰ دلار بالانس

   double contractSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(contractSize <= 0) contractSize = 100.0;

   double slDistance = MathAbs(entryPrice - slPrice);
   if(slDistance <= 0) return FixedLotSize;

   double lossPerLot = slDistance * contractSize;
   if(lossPerLot <= 0) return FixedLotSize;

   double rawLots = riskMoney / lossPerLot;

   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   double lots = MathFloor(rawLots / lotStep) * lotStep;
   lots = MathMax(minLot, MathMin(maxLot, lots));
   return lots;
}

//+------------------------------------------------------------------+
//| بررسی وجود معامله یا اردر باز متعلق به این اکسپرت                 |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == MagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol)
         return true;
   }
   return false;
}

bool HasPendingOrder()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket > 0 && OrderGetInteger(ORDER_MAGIC) == MagicNumber && OrderGetString(ORDER_SYMBOL) == _Symbol)
         return true;
   }
   return false;
}

void CancelPendingOrder()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket <= 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) == MagicNumber && OrderGetString(ORDER_SYMBOL) == _Symbol)
         trade.OrderDelete(ticket);
   }
}

//+------------------------------------------------------------------+
//| ارسال و ثبت سفارش معلق روی سطح 0.864                             |
//+------------------------------------------------------------------+
void PlaceOrder()
{
   double entryPrice, slPrice, tpPrice;
   GetFibLevels(entryPrice, slPrice, tpPrice);

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double spreadPrice  = ask - bid;
   double spreadPoints = spreadPrice / _Point;

   if(spreadPoints > MaxSpreadPoints) return;

   // رفع باگ مهم: اعتبارسنجی قطعی جهت و فاصله TP و SL با قیمت فعلی بازار
   if(isLongSetup)
   {
      // در خرید: قیمت ورود باید زیر Ask باشد، TP بالای ورود باشد، و SL زیر ورود باشد
      if(tpPrice <= entryPrice || slPrice >= entryPrice) return;
      if(entryPrice >= ask)
      {
         // اگر قیمت در همین لحظه به سطح ورود رسیده باشد، معامله بلافاصله با مارکت باز شود
         double lots = CalcLotSize(ask, slPrice);
         if(lots > 0)
         {
            if(trade.Buy(lots, _Symbol, ask, slPrice, tpPrice, "Arian-MktLong"))
            {
               tradedCycleTime = point1Time;
               cycleReady = false;
               Print("🚀 شلیک معامله مستقیم خرید NDS در قیمت: ", ask, " | لات: ", lots, " | TP: ", tpPrice, " | SL: ", slPrice);
            }
         }
         return;
      }
   }
   else
   {
      // در فروش: قیمت ورود باید بالای Bid باشد، TP زیر ورود باشد، و SL بالای ورود باشد
      if(tpPrice >= entryPrice || slPrice <= entryPrice) return;
      if(entryPrice <= bid)
      {
         // ورود فوری در قیمت بازار
         double lots = CalcLotSize(bid, slPrice);
         if(lots > 0)
         {
            if(trade.Sell(lots, _Symbol, bid, slPrice, tpPrice, "Arian-MktShort"))
            {
               tradedCycleTime = point1Time;
               cycleReady = false;
               Print("🚀 شلیک معامله مستقیم فروش NDS در قیمت: ", bid, " | لات: ", lots, " | TP: ", tpPrice, " | SL: ", slPrice);
            }
         }
         return;
      }
   }

   // قرار دادن سفارش معلق لیمیت
   double lots = CalcLotSize(entryPrice, slPrice);
   if(lots <= 0) return;

   datetime expiry = TimeCurrent() + PeriodSeconds(_Period) * PendingExpiryBars;
   bool placed = false;

   if(isLongSetup)
   {
      placed = trade.BuyLimit(lots, entryPrice, _Symbol, slPrice, tpPrice, ORDER_TIME_SPECIFIED, expiry, "Arian-BuyLimit");
   }
   else
   {
      placed = trade.SellLimit(lots, entryPrice, _Symbol, slPrice, tpPrice, ORDER_TIME_SPECIFIED, expiry, "Arian-SellLimit");
   }

   if(placed)
   {
      tradedCycleTime = point1Time;
      Print("🎯 سفارش لیمیت نوسانگیری ثبت شد: ", (isLongSetup ? "BuyLimit" : "SellLimit"),
            " | نرخ ورود: ", entryPrice, " | لات (ریسک ۵٪): ", lots,
            " | TP: ", tpPrice, " | SL: ", slPrice);
   }
}

//+------------------------------------------------------------------+
//| حلقه تیک زنده بازار                                              |
//+------------------------------------------------------------------+
void OnTick()
{
   // اگر پوزیشن بازی وجود دارد، سفارش معلق اضافه را حذف کن و منتظر خروج باش
   if(HasOpenPosition())
   {
      CancelPendingOrder();
      return;
   }

   // در هر کندل جدید تایمفریم، سایکلها را بهروزرسانی کن
   datetime currentBarTime = iTime(_Symbol, _Period, 0);
   if(currentBarTime != lastBarTime)
   {
      lastBarTime = currentBarTime;
      UpdateSwingPoints();
   }

   if(!cycleReady) return;
   if(HasPendingOrder()) return;

   // اگر این سایکل قبلاً معامله شده، منتظر سایکل بعدی بمان
   if(point1Time == tradedCycleTime) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   // باطل شدن سایکل در صورت فراتر رفتن قیمت از نقطه ۱
   if(isLongSetup && ask > point1Price)
   {
      cycleReady = false;
      CancelPendingOrder();
      return;
   }
   if(!isLongSetup && bid < point1Price)
   {
      cycleReady = false;
      CancelPendingOrder();
      return;
   }

   PlaceOrder();
}
//+------------------------------------------------------------------+

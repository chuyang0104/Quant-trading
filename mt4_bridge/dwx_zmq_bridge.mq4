//+------------------------------------------------------------------+
//|                                            dwx_zmq_bridge.mq4    |
//|                                    MT4 ZeroMQ Bridge for Python  |
//|                                                                  |
//+------------------------------------------------------------------+
#property copyright "Quant-trading Project"
#property link      "https://github.com"
#property version   "1.00"
#property strict

/**
 * MT4 ZeroMQ 桥接 EA
 *
 * 这是一个简化版的 ZeroMQ 桥接 EA，用于 MT4 与 Python 通信。
 *
 * 安装说明:
 * 1. 需要 ZeroMQ 库支持 - 使用 libzmq.dll (x86/x64)
 *    下载地址: https://github.com/zeromq/libzmq/releases
 *    将 libzmq.dll 放在 MQL4\\Libraries 目录或系统路径中
 *
 * 2. 将此 EA 编译后附加到任意图表
 *    建议附加到 VPS 常开品种的图表上
 *
 * 3. EA 默认监听端口:
 *    - 5555: REQ/REP 命令端口 (Python 发送命令)
 *    - 5556: PUSH/PULL 推送端口 (预留，用于事件推送)
 *
 * 4. Python 端使用 MT4Connector 类与此 EA 通信
 *    参考: core/mt4_connector.py
 *
 * 支持的命令 (通过 ZMQ 接收 JSON，处理后返回 JSON):
 * - {"action": "ping"} -> 测试连接
 * - {"action": "account_info"} -> 返回账户信息
 * - {"action": "copy_rates", "symbol": "XAUUSD", "timeframe": 60, "start": 0, "count": 100} -> 返回K线
 * - {"action": "symbol_info_tick", "symbol": "XAUUSD"} -> 返回bid/ask
 * - {"action": "symbols_get", "pattern": ""} -> 返回品种列表
 * - {"action": "symbol_info", "symbol": "XAUUSD"} -> 返回品种详情
 * - {"action": "order_send", "symbol": "XAUUSD", "type": 0, "volume": 0.1, ...} -> 下单
 * - {"action": "positions_get", "symbol": "XAUUSD"} -> 返回持仓列表
 * - {"action": "positions_total"} -> 返回持仓数量
 *
 * 注意: MT4 没有官方 Python API，ZeroMQ 是最可靠的桥接方式。
 */

#include <Zmq/Zmq.mqh>  // 需要 MT4-ZMQ 库支持

// 输入参数
input string REP_HOST = "tcp://*:5555";     // REP 监听地址
input string PUSH_HOST = "tcp://*:5556";    // PUSH 监听地址
input int    TIMEOUT = 5000;                // 超时时间(毫秒)

// ZeroMQ 上下文和 Socket
Context context("MT4_Bridge");
Socket repSocket(context, ZMQ_REP);
Socket pushSocket(context, ZMQ_PUSH);

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("===============================================");
    Print("MT4 ZeroMQ 桥接 EA 启动中...");
    Print("REP 监听地址: ", REP_HOST);
    Print("PUSH 监听地址: ", PUSH_HOST);
    Print("===============================================");

    // 初始化 REP Socket
    if(!repSocket.bind(REP_HOST)) {
        Print("错误: 无法绑定 REP socket 到 ", REP_HOST);
        return INIT_FAILED;
    }

    // 初始化 PUSH Socket (预留，用于事件推送)
    if(!pushSocket.bind(PUSH_HOST)) {
        Print("警告: 无法绑定 PUSH socket 到 ", PUSH_HOST);
        // 继续运行，PUSH 是可选的
    }

    Print("MT4 ZeroMQ 桥接 EA 启动成功!");
    Print("等待 Python 连接...");

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("MT4 ZeroMQ 桥接 EA 停止中...");

    repSocket.unbind(REP_HOST);
    pushSocket.unbind(PUSH_HOST);

    Print("MT4 ZeroMQ 桥接 EA 已停止。");
}

//+------------------------------------------------------------------+
//| Expert tick function                                               |
//+------------------------------------------------------------------+
void OnTick()
{
    // 处理 ZMQ 消息
    ZmqMsg request;

    // 非阻塞接收消息
    if(repSocket.recv(request, true)) {
        string jsonRequest = request.getData();

        // 处理请求并生成响应
        string jsonResponse = HandleRequest(jsonRequest);

        // 发送响应
        ZmqMsg response(jsonResponse);
        repSocket.send(response);
    }
}

//+------------------------------------------------------------------+
//| 处理 JSON 请求                                                    |
//+------------------------------------------------------------------+
string HandleRequest(string jsonRequest)
{
    // 简化处理 - 实际应使用 JSON 解析库
    // 这里演示基本结构

    string response = "";

    // 解析 action 字段 (简化实现)
    if(StringFind(jsonRequest, "\"action\": \"ping\"") >= 0) {
        response = HandlePing();
    }
    else if(StringFind(jsonRequest, "\"action\": \"account_info\"") >= 0) {
        response = HandleAccountInfo();
    }
    else if(StringFind(jsonRequest, "\"action\": \"copy_rates\"") >= 0) {
        response = HandleCopyRates(jsonRequest);
    }
    else if(StringFind(jsonRequest, "\"action\": \"symbol_info_tick\"") >= 0) {
        response = HandleSymbolInfoTick(jsonRequest);
    }
    else if(StringFind(jsonRequest, "\"action\": \"symbols_get\"") >= 0) {
        response = HandleSymbolsGet(jsonRequest);
    }
    else if(StringFind(jsonRequest, "\"action\": \"symbol_info\"") >= 0) {
        response = HandleSymbolInfo(jsonRequest);
    }
    else if(StringFind(jsonRequest, "\"action\": \"order_send\"") >= 0) {
        response = HandleOrderSend(jsonRequest);
    }
    else if(StringFind(jsonRequest, "\"action\": \"positions_get\"") >= 0) {
        response = HandlePositionsGet(jsonRequest);
    }
    else if(StringFind(jsonRequest, "\"action\": \"positions_total\"") >= 0) {
        response = HandlePositionsTotal();
    }
    else {
        response = "{\"status\": \"error\", \"message\": \"未知命令\"}";
    }

    return response;
}

//+------------------------------------------------------------------+
//| 处理 ping 命令                                                    |
//+------------------------------------------------------------------+
string HandlePing()
{
    return "{\"status\": \"success\", \"message\": \"pong\"}";
}

//+------------------------------------------------------------------+
//| 处理 account_info 命令                                             |
//+------------------------------------------------------------------+
string HandleAccountInfo()
{
    int login = AccountInfoInteger(ACCOUNT_LOGIN);
    string server = AccountInfoString(ACCOUNT_SERVER);
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
    double margin = AccountInfoDouble(ACCOUNT_MARGIN);
    double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
    double marginLevel = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
    string currency = AccountInfoString(ACCOUNT_CURRENCY);
    int leverage = AccountInfoInteger(ACCOUNT_LEVERAGE);
    double profit = AccountInfoDouble(ACCOUNT_PROFIT);

    StringResize(response, 500);
    sprintf(response, "{\"status\": \"success\", \"data\": {" +
                     "\"login\": %d, " +
                     "\"server\": \"%s\", " +
                     "\"balance\": %.2f, " +
                     "\"equity\": %.2f, " +
                     "\"margin\": %.2f, " +
                     "\"free_margin\": %.2f, " +
                     "\"margin_level\": %.2f, " +
                     "\"currency\": \"%s\", " +
                     "\"leverage\": %d, " +
                     "\"profit\": %.2f" +
                     "}}",
                     login, server, balance, equity, margin, freeMargin,
                     marginLevel, currency, leverage, profit);

    return response;
}

//+------------------------------------------------------------------+
//| 处理 copy_rates 命令                                               |
//+------------------------------------------------------------------+
string HandleCopyRates(string jsonRequest)
{
    // 解析参数 (简化实现)
    string symbol = ExtractJsonValue(jsonRequest, "symbol");
    int timeframe = ExtractJsonInt(jsonRequest, "timeframe");
    int start = ExtractJsonInt(jsonRequest, "start");
    int count = ExtractJsonInt(jsonRequest, "count");

    if(count <= 0 || count > 1000) count = 100;
    if(start < 0) start = 0;

    // 构建响应
    string response = "{\"status\": \"success\", \"data\": [";

    for(int i = start; i < start + count && i < Bars(symbol, timeframe); i++) {
        if(i > start) response += ",";

        datetime time = iTime(symbol, timeframe, i);
        double open = iOpen(symbol, timeframe, i);
        double high = iHigh(symbol, timeframe, i);
        double low = iLow(symbol, timeframe, i);
        double close = iClose(symbol, timeframe, i);
        long volume = iVolume(symbol, timeframe, i);
        int spread = 0; // MT4 无法直接获取历史K线点差

        StringAdd(response, "{");
        StringAdd(response, "\"time\": " + IntegerToString(TimeCurrent(time)));
        StringAdd(response, ", \"open\": " + DoubleToString(open, 5));
        StringAdd(response, ", \"high\": " + DoubleToString(high, 5));
        StringAdd(response, ", \"low\": " + DoubleToString(low, 5));
        StringAdd(response, ", \"close\": " + DoubleToString(close, 5));
        StringAdd(response, ", \"tick_volume\": " + IntegerToString(volume));
        StringAdd(response, ", \"spread\": " + IntegerToString(spread));
        StringAdd(response, "}");
    }

    StringAdd(response, "]}");
    return response;
}

//+------------------------------------------------------------------+
//| 处理 symbol_info_tick 命令                                         |
//+------------------------------------------------------------------+
string HandleSymbolInfoTick(string jsonRequest)
{
    string symbol = ExtractJsonValue(jsonRequest, "symbol");

    if(symbol == "") symbol = Symbol();

    double bid = MarketInfo(symbol, MODE_BID);
    double ask = MarketInfo(symbol, MODE_ASK);
    double point = MarketInfo(symbol, MODE_POINT);

    StringResize(response, 200);
    sprintf(response, "{\"status\": \"success\", \"data\": {" +
                     "\"symbol\": \"%s\", " +
                     "\"bid\": %.5f, " +
                     "\"ask\": %.5f, " +
                     "\"last\": %.5f, " +
                     "\"time\": %d" +
                     "}}",
                     symbol, bid, ask, ask, TimeCurrent());

    return response;
}

//+------------------------------------------------------------------+
//| 处理 symbols_get 命令                                              |
//+------------------------------------------------------------------+
string HandleSymbolsGet(string jsonRequest)
{
    string pattern = ExtractJsonValue(jsonRequest, "pattern");

    string response = "{\"status\": \"success\", \"data\": [";

    for(int i = 0; i < SymbolsTotal(true); i++) {
        string symbol = SymbolName(i, true);

        // 简单的模式匹配
        if(pattern != "" && StringFind(symbol, pattern) < 0) continue;

        if(i > 0) response += ",";
        StringAdd(response, "\"" + symbol + "\"");
    }

    StringAdd(response, "]}");
    return response;
}

//+------------------------------------------------------------------+
//| 处理 symbol_info 命令                                              |
//+------------------------------------------------------------------+
string HandleSymbolInfo(string jsonRequest)
{
    string symbol = ExtractJsonValue(jsonRequest, "symbol");

    if(symbol == "" || !IsSymbolExist(symbol)) {
        return "{\"status\": \"error\", \"message\": \"品种不存在\"}";
    }

    double point = MarketInfo(symbol, MODE_POINT);
    int digits = (int)MarketInfo(symbol, MODE_DIGITS);
    double minLot = MarketInfo(symbol, MODE_MINLOT);
    double maxLot = MarketInfo(symbol, MODE_MAXLOT);
    double lotStep = MarketInfo(symbol, MODE_LOTSTEP);
    double contractSize = MarketInfo(symbol, MODE_LOTSIZE);
    double bid = MarketInfo(symbol, MODE_BID);
    double ask = MarketInfo(symbol, MODE_ASK);
    int spread = (int)MarketInfo(symbol, MODE_SPREAD);

    StringResize(response, 500);
    sprintf(response, "{\"status\": \"success\", \"data\": {" +
                     "\"name\": \"%s\", " +
                     "\"point\": %.5f, " +
                     "\"digits\": %d, " +
                     "\"volume_min\": %.2f, " +
                     "\"volume_max\": %.2f, " +
                     "\"volume_step\": %.2f, " +
                     "\"contract_size\": %.0f, " +
                     "\"bid\": %.5f, " +
                     "\"ask\": %.5f, " +
                     "\"spread\": %d" +
                     "}}",
                     symbol, point, digits, minLot, maxLot, lotStep,
                     contractSize, bid, ask, spread);

    return response;
}

//+------------------------------------------------------------------+
//| 处理 order_send 命令                                               |
//+------------------------------------------------------------------+
string HandleOrderSend(string jsonRequest)
{
    string symbol = ExtractJsonValue(jsonRequest, "symbol");
    int type = ExtractJsonInt(jsonRequest, "type");  // 0=BUY, 1=SELL
    double volume = ExtractJsonDouble(jsonRequest, "volume");
    double price = ExtractJsonDouble(jsonRequest, "price");
    double sl = ExtractJsonDouble(jsonRequest, "sl");
    double tp = ExtractJsonDouble(jsonRequest, "tp");
    int magic = ExtractJsonInt(jsonRequest, "magic");
    string comment = ExtractJsonValue(jsonRequest, "comment");
    int deviation = ExtractJsonInt(jsonRequest, "deviation");

    if(symbol == "") {
        return "{\"status\": \"error\", \"message\": \"缺少品种代码\"}";
    }

    // 准备订单结构
    MqlTradeRequest request;
    MqlTradeResult result;

    ZeroMemory(request);
    ZeroMemory(result);

    request.action = TRADE_ACTION_DEAL;
    request.symbol = symbol;
    request.volume = volume;
    request.type = (type == 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
    request.price = price;
    request.sl = sl;
    request.tp = tp;
    request.deviation = deviation;
    request.magic = magic;
    request.comment = comment;

    // 市价单不需要价格
    if(request.price == 0) {
        if(request.type == ORDER_TYPE_BUY)
            request.price = MarketInfo(symbol, MODE_ASK);
        else
            request.price = MarketInfo(symbol, MODE_BID);
    }

    // 发送订单 (注意: MT4 使用 OrderSend)
    int ticket = OrderSend(
        symbol,
        (type == 0) ? OP_BUY : OP_SELL,
        volume,
        request.price,
        deviation,
        sl,
        tp,
        comment,
        magic,
        0,
        clrNONE
    );

    if(ticket > 0) {
        StringResize(response, 200);
        sprintf(response, "{\"status\": \"success\", \"ticket\": %d, \"message\": \"下单成功\"}", ticket);
        return response;
    } else {
        int error = GetLastError();
        StringResize(response, 200);
        sprintf(response, "{\"status\": \"error\", \"code\": %d, \"message\": \"下单失败: %s\"}",
                 error, ErrorDescription(error));
        return response;
    }
}

//+------------------------------------------------------------------+
//| 处理 positions_get 命令                                            |
//+------------------------------------------------------------------+
string HandlePositionsGet(string jsonRequest)
{
    string symbol = ExtractJsonValue(jsonRequest, "symbol");
    string response = "{\"status\": \"success\", \"data\": [";

    bool first = true;

    for(int i = OrdersTotal() - 1; i >= 0; i--) {
        if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) {
            // 过滤品种
            if(symbol != "" && OrderSymbol() != symbol) continue;

            if(!first) response += ",";
            first = false;

            StringAdd(response, "{");
            StringAdd(response, "\"ticket\": " + IntegerToString(OrderTicket()));
            StringAdd(response, ", \"symbol\": \"" + OrderSymbol() + "\"");
            StringAdd(response, ", \"type\": " + IntegerToString(OrderType()));  // 0=BUY, 1=SELL
            StringAdd(response, ", \"volume\": " + DoubleToString(OrderLots(), 2));
            StringAdd(response, ", \"price_open\": " + DoubleToString(OrderOpenPrice(), 5));

            double currentPrice = (OrderType() == OP_BUY) ?
                                 MarketInfo(OrderSymbol(), MODE_BID) :
                                 MarketInfo(OrderSymbol(), MODE_ASK);
            StringAdd(response, ", \"price_current\": " + DoubleToString(currentPrice, 5));
            StringAdd(response, ", \"sl\": " + DoubleToString(OrderStopLoss(), 5));
            StringAdd(response, ", \"tp\": " + DoubleToString(OrderTakeProfit(), 5));

            double profit = OrderProfit();
            StringAdd(response, ", \"profit\": " + DoubleToString(profit, 2));
            StringAdd(response, ", \"comment\": \"" + OrderComment() + "\"");
            StringAdd(response, "}");
        }
    }

    StringAdd(response, "]}");
    return response;
}

//+------------------------------------------------------------------+
//| 处理 positions_total 命令                                          |
//+------------------------------------------------------------------+
string HandlePositionsTotal()
{
    int count = 0;

    for(int i = 0; i < OrdersTotal(); i++) {
        if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) {
            // 只计算持仓(不挂单)
            if(OrderType() == OP_BUY || OrderType() == OP_SELL) {
                count++;
            }
        }
    }

    StringResize(response, 100);
    sprintf(response, "{\"status\": \"success\", \"data\": %d}", count);
    return response;
}

//+------------------------------------------------------------------+
//| 辅助函数: 检查品种是否存在                                         |
//+------------------------------------------------------------------+
bool IsSymbolExist(string symbol)
{
    for(int i = 0; i < SymbolsTotal(true); i++) {
        if(SymbolName(i, true) == symbol) return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| 辅助函数: 从 JSON 提取字符串值 (简化实现)                          |
//+------------------------------------------------------------------+
string ExtractJsonValue(string json, string key)
{
    // 简化实现 - 实际应使用 JSON 解析库
    string pattern = "\"" + key + "\": \"";
    int start = StringFind(json, pattern);

    if(start < 0) {
        // 尝试无引号格式
        pattern = "\"" + key + "\": \"";
        start = StringFind(json, pattern);
        if(start < 0) return "";
    }

    start += StringLen(pattern);
    int end = StringFind(json, "\"", start);

    if(end < 0) return "";

    return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
//| 辅助函数: 从 JSON 提取整数值 (简化实现)                            |
//+------------------------------------------------------------------+
int ExtractJsonInt(string json, string key)
{
    string pattern = "\"" + key + "\": ";
    int start = StringFind(json, pattern);

    if(start < 0) return 0;

    start += StringLen(pattern);

    // 找到下一个逗号或右括号
    int end = StringFind(json, ",", start);
    int braceEnd = StringFind(json, "}", start);

    if(end < 0 || (braceEnd >= 0 && braceEnd < end)) end = braceEnd;
    if(end < 0) return 0;

    string valueStr = StringSubstr(json, start, end - start);
    return (int)StringToInteger(valueStr);
}

//+------------------------------------------------------------------+
//| 辅助函数: 从 JSON 提取浮点数值 (简化实现)                          |
//+------------------------------------------------------------------+
double ExtractJsonDouble(string json, string key)
{
    string pattern = "\"" + key + "\": ";
    int start = StringFind(json, pattern);

    if(start < 0) return 0.0;

    start += StringLen(pattern);

    // 找到下一个逗号或右括号
    int end = StringFind(json, ",", start);
    int braceEnd = StringFind(json, "}", start);

    if(end < 0 || (braceEnd >= 0 && braceEnd < end)) end = braceEnd;
    if(end < 0) return 0.0;

    string valueStr = StringSubstr(json, start, end - start);
    return StringToDouble(valueStr);
}

//+------------------------------------------------------------------+

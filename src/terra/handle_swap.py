
import logging
from terra.make_tx import make_swap_tx
from terra.util_terra import _asset_to_currency, _float_amount
from terra import util_terra


def handle_swap_msgswap(exporter, elem, txinfo):
    txid = txinfo.txid
    wallet_address = txinfo.wallet_address

    transfers_in, transfers_out = util_terra._transfers(elem, wallet_address, txid)

    for i in range(len(transfers_in)):
        received_amount, received_currency = transfers_in[i]
        sent_amount, sent_currency = transfers_out[i]

        row = make_swap_tx(txinfo, sent_amount, sent_currency, received_amount, received_currency,
                           txid=txid, empty_fee=(i > 0))
        exporter.ingest_row(row)


def handle_swap(exporter, elem, txinfo):
    logs = elem["logs"]

    if "coin_received" in logs[0]["events_by_type"]:
        for log in logs:
            _handle_log(exporter, txinfo, log)
    else:
        # older version of data
       _handle_swap(exporter, elem, txinfo)

def handle_execute_swap_operations(exporter, elem, txinfo):
    logs = elem["logs"]

    if "coin_received" in logs[0]["events_by_type"]:
        for log in logs:
            _handle_log(exporter, txinfo, log)
    else:
        # older version of data
        _handle_execute_swap_operations(exporter, elem, txinfo)


def _handle_log(exporter, txinfo, log):
    wallet_address = txinfo.wallet_address

    coin_received = log["events_by_type"]["coin_received"]
    coin_spent = log["events_by_type"]["coin_spent"]

    amounts = coin_received["amount"]
    receivers = coin_received["receiver"]
    received = [amounts[i] for i in range(len(amounts)) if receivers[i] == wallet_address]

    amounts = coin_spent["amount"]
    spenders = coin_spent["spender"]
    sent = [amounts[i] for i in range(len(amounts)) if spenders[i] == wallet_address]

    if len(received) == 1 and len(sent) == 1:
        amount_string_received = received[0]
        amount_string_sent = sent[0]

        received_amount, received_currency = util_terra._amount(amount_string_received)
        sent_amount, sent_currency = util_terra._amount(amount_string_sent)

        row = make_swap_tx(txinfo, sent_amount, sent_currency, received_amount, received_currency)
        exporter.ingest_row(row)

    else:
        raise Exception("Bad condition in _handle_log()")


def _handle_swap(exporter, elem, txinfo):
    txid = txinfo.txid
    from_contract = util_terra._event_with_action(elem, "from_contract", "swap")

    # Determine send amount, currency
    sent_amount, sent_currency = _sent(from_contract, txid)

    # Determine receive amount, currency
    receive_amount, receive_currency = _received(from_contract, txid)

    row = make_swap_tx(txinfo, sent_amount, sent_currency, receive_amount, receive_currency)
    exporter.ingest_row(row)


def _handle_execute_swap_operations(exporter, elem, txinfo):
    txid = txinfo.txid
    wallet_address = txinfo.wallet_address

    transfers_in, transfers_out = util_terra._transfers(elem, wallet_address, txid)

    try:
        from_contract = elem["logs"][0]["events_by_type"]["from_contract"]

        # Determine send amount, currency
        if transfers_out:
            sent_amount, sent_currency = transfers_out[0]
        else:
            sent_amount, sent_currency = _sent(from_contract, txid)

        # Determine receive amount, currency
        if transfers_in:
            receive_amount, receive_currency = transfers_in[0]
        else:
            receive_amount, receive_currency = _received(from_contract, txid)

        row = make_swap_tx(txinfo, sent_amount, sent_currency, receive_amount, receive_currency)
        exporter.ingest_row(row)

        return
    except Exception as e:
        logging.error("error in handle_execute_swap_operations()")
        raise e


def _sent(from_contract, txid):
    offer_amount = from_contract["offer_amount"][0]
    offer_asset = from_contract["offer_asset"][0]

    # Determine currency
    send_currency = _asset_to_currency(offer_asset, txid)

    # Determine amount
    send_amount = _float_amount(offer_amount, send_currency)

    return send_amount, send_currency


def _received(from_contract, txid):
    last_return_amount = from_contract["return_amount"][-1]
    last_asset = from_contract["ask_asset"][-1]
    last_tax_amount = from_contract["tax_amount"][-1]

    # Determine currency
    receive_currency = _asset_to_currency(last_asset, txid)

    # Determine amount
    receive_amount = (_float_amount(last_return_amount, receive_currency)
                      - _float_amount(last_tax_amount, receive_currency))

    return receive_amount, receive_currency
def check_onchain_fact(payload: dict, chain) -> dict:
    """chain provides get_balance/tx_exists/block_number. Returns a proof dict."""
    block = chain.block_number()
    check = payload.get("check")
    try:
        if check == "balance_gte":
            ok = chain.get_balance(payload["address"]) >= payload["min"]
            return {"result": bool(ok), "block": block}
        if check == "tx_exists":
            return {"result": bool(chain.tx_exists(payload["hash"])), "block": block}
        return {"result": False, "block": block,
                "reason": f"unsupported check: {check!r}"}
    except Exception as e:
        return {"result": False, "block": block, "reason": f"read failed: {e}"}

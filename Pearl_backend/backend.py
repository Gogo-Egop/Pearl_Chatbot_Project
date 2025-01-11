from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import db_helpmate
import generic_helper

app = FastAPI()

# initialize global variable
inprogress_orders = {}

@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI chatbot backend!"}

@app.post("/")
async def handle_request(request: Request):
    # Retrieve the JSON data from the request
    payload = await request.json()

    # Extract the necessary information from the payload
    intent = payload['queryResult']['intent']['displayName'].split(" - context")[0]
    parameters = payload['queryResult']['parameters']
    output_contexts = payload['queryResult'].get('outputContexts', [])
    session_id = generic_helper.extract_session_id(output_contexts[0]["name"]) if output_contexts else "unknown_session"

    # Log extracted data for debugging
    print(f"Intent: {intent}")
    print(f"Parameters: {parameters}")
    print(f"Output Contexts: {output_contexts}")
    print(f"Session ID: {session_id}")

    # Updated intent handler dictionary
    # Updated intent handler dictionary to handle 'order.add' correctly
    # Updated intent handler dictionary
    # Updated intent handler dictionary
    intent_handler_dict = {
        'order.add': add_to_order,  # Adding items to order
        'order.add - context: ongoing-order': add_to_order,
        'order.complete': complete_order,  # Completing order
        'order.complete - context: ongoing-order': complete_order,
        'order.remove': remove_from_order,  # Adding 'order.remove' for cases without context
        'order.remove - context: ongoing-order': remove_from_order,  # Removing items with context
        'track.order': track_order,  # Track order without context
        'track.order - context: ongoing-tracking': track_order  # Track order with context
    }

    # Handle the intent or return a default response if the intent isn't mapped
    if intent in intent_handler_dict:
        return intent_handler_dict[intent](parameters, session_id)
    else:
        return JSONResponse(content={
            "fulfillmentText": f"Sorry, I don't know how to handle the intent '{intent}'."
        })


def save_to_db(order: dict):
    next_order_id = db_helpmate.get_next_order_id()

    # Insert individual items along with quantity in orders table
    for food_item, quantity in order.items():
        rcode = db_helpmate.insert_order_item(
            food_item,
            quantity,
            next_order_id
        )

        if rcode == -1:
            return -1

    # Now insert order tracking status
    db_helpmate.insert_order_tracking(next_order_id, "in progress")

    return next_order_id


def complete_order(parameters: dict, session_id: str):
    if session_id not in inprogress_orders:
        fulfillment_text = "I'm having trouble finding your order. Sorry! Can you place a new order please?"
    else:
        order = inprogress_orders[session_id]
        order_id = save_to_db(order)
        if order_id == -1:
            fulfillment_text = "Sorry, I couldn't process your order due to a backend error. " \
                               "Please place a new order again."
        else:
            order_total = db_helpmate.get_total_order_price(order_id)

            fulfillment_text = f"Awesome. We have placed your order. " \
                               f"Here is your order id # {order_id}. " \
                               f"Your order total is {order_total} which you can pay at the time of delivery!"

        del inprogress_orders[session_id]

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })


def add_to_order(parameters: dict, session_id: str):
    food_items = parameters["food-item"]
    quantities = parameters["number"]

    if len(food_items) != len(quantities):
        fulfillment_text = "Sorry I didn't understand. Can you please specify food items and quantities clearly?"
    else:
        new_food_dict = dict(zip(food_items, quantities))

        if session_id in inprogress_orders:
            current_food_dict = inprogress_orders[session_id]
            current_food_dict.update(new_food_dict)
            inprogress_orders[session_id] = current_food_dict
        else:
            inprogress_orders[session_id] = new_food_dict

        order_str = generic_helper.get_str_from_food_dict(inprogress_orders[session_id])
        fulfillment_text = f"So far you have: {order_str}. Do you need anything else?"

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })


def remove_from_order(parameters: dict, session_id: str):
    if session_id not in inprogress_orders:
        return JSONResponse(content={
            "fulfillmentText": "I'm having a trouble finding your order. Sorry! Can you place a new order please?"
        })

    food_items = parameters["food-item"]
    current_order = inprogress_orders[session_id]

    removed_items = []
    no_such_items = []

    for item in food_items:
        if item not in current_order:
            no_such_items.append(item)
        else:
            removed_items.append(item)
            del current_order[item]

    if len(removed_items) > 0:
        fulfillment_text = f'Removed {",".join(removed_items)} from your order!'

    if len(no_such_items) > 0:
        fulfillment_text = f' Your current order does not have {",".join(no_such_items)}'

    if len(current_order.keys()) == 0:
        fulfillment_text += " Your order is empty!"
    else:
        order_str = generic_helper.get_str_from_food_dict(current_order)
        fulfillment_text += f" Here is what is left in your order: {order_str}"

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })


def track_order(parameters: dict, session_id: str):
    # Check if 'order_id' exists in the parameters
    if 'order_id' not in parameters:
        fulfillment_text = "I need an order ID to track your order. Please provide the order ID."
    else:
        order_id = int(parameters['order_id'])
        order_status = db_helpmate.get_order_status(order_id)

        if order_status:
            fulfillment_text = f"The order status for order ID {order_id} is: {order_status}"
        else:
            fulfillment_text = f"No order found with order ID {order_id}. Please check the order ID and try again."

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })





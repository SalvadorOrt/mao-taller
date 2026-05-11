from .navigation import get_menu_lateral

def menu_lateral(request):
    if not request.user.is_authenticated:
        return {"menu_lateral": []}

    return {
        "menu_lateral": get_menu_lateral(request.user)
    }
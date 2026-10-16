from django.urls import path
from wallet.views import my_wallet,create_wallet_topup,verify_wallet_topup

app_name ="wallet"

urlpatterns=[
    path("", my_wallet,name="my_wallet"),
    path("topup/create/", create_wallet_topup,name="create_wallet_topup"),
    path("topup/verify", verify_wallet_topup, name="verify_wallet_topup"),
]
{
    "name": "Purchase Auto Landed Cost Creation",
    "summary": """
        Purchase Auto Landed Cost Creation
    """,
    "description": """
        Create landed costs directly from purchase order.
    """,
    "author": "Sanesquare Technologies",
    "website": "https://www.sanesquare.com/",
    "support": "odoo@sanesquare.com",
    "license": "AGPL-3",
    "category": "Purchase",
    "version": "16.0.1.0.1",
    "images": ["static/description/app_image.png"],
    "depends": ["base", "stock", "purchase", "stock_landed_costs"],
    "data": [
        "views/purchase_views.xml",
        "views/stock_valuation_adjustment.xml",
        "views/stock_landed_cost_views.xml",
        "security/ir.model.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "ssq_purchase_auto_landed_cost_creation/static/src/js/action_manager.js",
        ]
    },
}

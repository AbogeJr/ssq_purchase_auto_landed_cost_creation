from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    landed_cost_lines = fields.One2many(
        "purchase.landed.cost.line", "purchase_id", "Landed Costs"
    )
    landed_costs_ids = fields.Many2many("stock.landed.cost")

    def create_landed_cost(self):
        self.ensure_one()
        purchase_line_ids = self.env["purchase.order.line"].search(
            [("order_id", "=", self.id)]
        )
        print("\n\n===PURCHASE LINE IDS===")
        print(purchase_line_ids)
        print(purchase_line_ids.invoice_lines)
        print(purchase_line_ids.invoice_lines.move_id)

        invoice = False
        draft_landed_costs = self.landed_cost_lines.search(
            [
                ("is_landed_cost_created", "=", False),
            ]
        )
        if draft_landed_costs:
            landed_costs_per_vendor = {}
            for line in draft_landed_costs:
                if line.vendor_id.id not in landed_costs_per_vendor:
                    landed_costs_per_vendor[line.vendor_id.id] = []
                landed_costs_per_vendor[line.vendor_id.id].append(line)

            AccountMove = self.env["account.move"]
            AccountMoveLine = self.env["account.move.line"]

            vb_ids = []
            # for line in draft_landed_costs:
            for vendor_id, landed_costs in landed_costs_per_vendor.items():
                invoice = AccountMove.create(
                    {
                        "move_type": "in_invoice",
                        "partner_id": vendor_id,  # Set the customer/partner for the invoice
                        "invoice_date": datetime.now().date(),  # Set the invoice date
                        "ref": self.name,  # Set the invoice reference
                    }
                )

                vb_ids.append(invoice.id)

                for item in landed_costs:
                    line = AccountMoveLine.create(
                        {
                            "name": item.name,
                            "product_id": item.product_id.id,
                            "tax_ids": [(6, 0, item.product_id.taxes_id.ids)],
                            "price_unit": item.product_id.list_price,
                            "is_landed_costs_line": True,
                            "purchase_order_id": self.id,
                            "move_id": invoice.id,
                            "purchase_line_id": purchase_line_ids.id,
                        }
                    )

                invoice.write(
                    {
                        "invoice_line_ids": [
                            (4, line.id),
                        ]
                    }
                )

            line_data = []
            for item in draft_landed_costs:
                line_data.append(
                    (
                        0,
                        0,
                        {
                            "product_id": item.product_id.id,
                            "name": item.name,
                            "account_id": item.account_id.id,
                            "split_method": item.split_method,
                            "price_unit": item.price_unit,
                        },
                    )
                )
                item.is_landed_cost_created = True
            landed_cost = self.env["stock.landed.cost"].create(
                {
                    "vendor_bill_id": invoice.id,
                    "vendor_bill_ids": vb_ids,
                    "date": datetime.now().date(),
                    "purchase_id": self.id,
                    "picking_ids": self.picking_ids,
                    "cost_lines": line_data,
                }
            )
            self.sudo().landed_costs_ids = [(4, landed_cost.id)]
            self.sudo().invoice_status = "invoiced"

    def action_view_landed_costs(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_landed_costs.action_stock_landed_cost"
        )
        domain = [("id", "in", self.landed_costs_ids.ids)]
        context = dict(self.env.context, default_purchase_id=self.id)
        views = [
            (
                self.env.ref(
                    "ssq_purchase_auto_landed_cost_creation.view_stock_landed_cost_tree"
                ).id,
                "tree",
            ),
            (False, "form"),
            (False, "kanban"),
        ]
        return dict(action, domain=domain, context=context, views=views)


class PurchaseLandedCost(models.Model):
    _name = "purchase.landed.cost.line"

    name = fields.Char("Description")
    vendor_id = fields.Many2one("res.partner", "Vendor")
    product_id = fields.Many2one(
        "product.product",
        "Product",
        domain=[("landed_cost_ok", "=", True)],
        required=True,
    )
    account_id = fields.Many2one("account.account", "Account")
    split_method = fields.Selection(
        [
            ("equal", "Equal"),
            ("by_quantity", "By Quantity"),
            ("by_current_cost_price", "By Current Cost"),
            ("by_weight", "By Weight"),
            ("by_volume", "By Volume"),
        ],
        "Split Method",
        default="equal",
        required=True,
    )
    price_unit = fields.Float("Cost")
    purchase_id = fields.Many2one("purchase.order")
    is_landed_cost_created = fields.Boolean(default=False)

    def unlink(self):
        for record in self:
            if record.is_landed_cost_created:
                raise UserError(_("You cannot delete a posted landed cost entry !!!"))
        return super(PurchaseLandedCost, self).unlink()

    @api.onchange("product_id")
    def onchange_product_id(self):
        self.name = self.product_id.name
        self.account_id = (
            self.product_id.property_account_expense_id.id
            or self.product_id.categ_id.property_account_expense_categ_id.id
        )

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
from odoo.tools import date_utils
import io
import json

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    landed_cost_lines = fields.One2many(
        "purchase.landed.cost.line", "purchase_id", "Landed Costs"
    )
    landed_costs_ids = fields.One2many(
        "stock.landed.cost", "purchase_id", string="Landed Costs"
    )

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
                            "account_id": item.account_id.id,
                            "price_unit": item.price_unit,
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

    def print_xlsx_report(self):
        datas = {
            "ids": self.ids,
            "model": "purchase.order",
            "options": json.dumps(
                {
                    "id": self.id,
                },
                default=date_utils.json_default,
            ),
            "output_format": "xlsx",
            "report_name": "Excel Report",
            "form": self.read()[0],
        }

        return {
            "type": "ir.actions.report",
            "report_name": "purchase_order_xlsx",
            "data": datas,
            "name": "Purchase Order",
            "file": "Purchase Order.xlsx",
            "report_type": "xlsx",
        }

    def get_xlsx_report(self, data, response):
        po = self.env["purchase.order"].search([("id", "=", data["id"])])

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet()
        header = workbook.add_format(
            {"font_size": 16, "align": "center", "bg_color": "#D3D3D3", "bold": True}
        )
        bold = workbook.add_format({"font_size": 10, "bold": True})
        normal = workbook.add_format({"font_size": 10})
        currency = workbook.add_format({"font_size": 10, "num_format": "#,##0.00"})
        currency_bold = workbook.add_format(
            {"font_size": 10, "num_format": "#,##0.00", "bold": True}
        )

        sheet.merge_range("B1:K1", "Purchase Order: %s" % po.name, header)
        sheet.merge_range("B2:C2", "Supplier:", bold)
        sheet.merge_range("D2:E2", po.partner_id.name, normal)
        sheet.merge_range("B3:C3", "Order Date:", bold)
        sheet.merge_range("D3:E3", po.date_order, normal)
        sheet.merge_range("B4:C4", "Currency:", bold)
        sheet.merge_range("D4:E4", po.currency_id.name, normal)

        # Adjust height: top row
        sheet.set_row(0, 20)

        # Adjust column sizes
        sheet.set_column(0, 0, 5)
        sheet.set_column(1, 1, 12)
        sheet.set_column(2, 2, 30)
        sheet.set_column(3, 3, 5)
        sheet.set_column(4, 4, 10)
        sheet.set_column(6, 6, 12)

        # Table Headers
        row = 4
        sheet.write(row, 0, "No.", bold)
        sheet.write(row, 1, "Product Sequence", bold)
        sheet.write(row, 2, "Automan ID", bold)
        sheet.write(row, 3, "Supplier Product Code", bold)
        sheet.write(row, 4, "Product Code", bold)
        sheet.write(row, 5, "Product Description", bold)
        sheet.write(row, 6, "Qty", bold)
        sheet.write(row, 7, "FoB", bold)
        sheet.write(row, 8, "Units", bold)
        sheet.write(row, 9, "Measurements", bold)
        sheet.write(row, 10, "Sub-total", bold)

        # Table data
        index = 1
        row += 1
        for line in po.order_line:
            product_code = line.product_id.default_code
            supplier_code = ""
            supplier = line.product_id.seller_ids.filtered(
                lambda s: s.partner_id.id == po.partner_id.id
            )
            if supplier:
                supplier_code = supplier[0].product_code
            sheet.write(row, 0, index, normal)
            sheet.write(row, 1, line.product_id.sequence, normal)
            sheet.write(row, 2, line.product_id.id or "", normal)
            sheet.write(row, 3, supplier_code or "N\A", normal)
            sheet.write(row, 4, product_code or "N\A", normal)
            sheet.write(row, 5, line.product_id.name, normal)
            sheet.write(row, 6, line.product_qty, normal)
            sheet.write(row, 7, line.price_unit, currency)
            sheet.write(row, 8, line.product_uom_qty, normal)
            sheet.write(row, 9, line.product_uom.name or "", normal)
            sheet.write(row, 10, line.price_subtotal, currency)

            row += 1
            index += 1

        # write sub-totals
        row += 1
        sheet.write(row, 9, "Taxes:", bold)
        sheet.write(row, 10, po.amount_tax, currency_bold)
        row += 1
        sheet.write(row, 9, "Totals:", bold)
        sheet.write(row, 10, po.amount_total, currency_bold)
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()


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

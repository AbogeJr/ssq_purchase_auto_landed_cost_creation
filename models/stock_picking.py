from odoo import fields, models
from datetime import datetime


class StockLandedCost(models.Model):
    _inherit = "stock.landed.cost"

    purchase_id = fields.Many2one("purchase.order")
    currency_factor = fields.Float(string="Currency Rate", default=1)
    landed_cost_factor = fields.Float(default=1)
    base_pricing_factor = fields.Float(default=1)
    pricing_preference = fields.Selection(
        [
            ("strict", "Strict"),
            ("high", "Prefer higher Price"),
            ("low", "Prefer Lower Price"),
        ]
    )
    vendor_bill_ids = fields.Many2many("account.move", string="Vendor Bills")
    cost_item_totals = fields.Float(
        string="Cost Item Totals", compute="_compute_cost_item_totals"
    )

    def _compute_cost_item_totals(self):
        for record in self:
            record.cost_item_totals = record.purchase_id.amount_total

    def button_validate(self):
        res = super(StockLandedCost, self).button_validate()
        for cost in self:
            for vendor_bill_id in cost.vendor_bill_ids:
                if (
                    vendor_bill_id
                    and vendor_bill_id.state == "posted"
                    and cost.company_id.anglo_saxon_accounting
                ):
                    all_amls = vendor_bill_id.line_ids | cost.account_move_id.line_ids
                    for product in cost.cost_lines.product_id:
                        accounts = product.product_tmpl_id.get_product_accounts()
                        input_account = accounts["stock_input"]
                        all_amls.filtered(
                            lambda aml: aml.account_id == input_account
                            and not aml.reconciled
                        ).reconcile()
                        print("Reconciled")
        return res

    def compute_landed_cost(self):
        res = super(StockLandedCost, self).compute_landed_cost()
        if self.purchase_id:
            total_purchase_qty = 0
            total_product_weight = 0
            total_product_volume = 0

            for line in self.purchase_id.order_line:
                total_purchase_qty += line.product_qty
                total_product_weight += line.product_id.weight * line.product_qty
                total_product_volume += line.product_id.volume * line.product_qty

            purchase_order_line_ids = []
            prev_former_cost = 0
            for line in self.env["stock.valuation.adjustment.lines"].search(
                [("cost_line_id", "=", self.cost_lines[0].id)]
            ):
                purchase_line_id = self.env["purchase.order.line"].search(
                    [
                        ("product_id", "=", line.product_id.id),
                        ("order_id", "=", self.purchase_id.id),
                        ("id", "not in", purchase_order_line_ids),
                    ],
                    limit=1,
                    order="id asc",
                )
                purchase_order_line_ids.append(purchase_line_id.id)
                prev_former_cost += (
                    line.former_cost / line.quantity * purchase_line_id.product_qty
                )

            purchase_order_line_ids = []
            cost_dict = {}
            for line in self.valuation_adjustment_lines:
                print("\n\n===VAD LINE===")
                print(line)
                print(line.former_cost)
                print(line.new_cost)
                print(line.cost_difference)
                print(line.cost_id.cost_lines[0].price_unit)
                landed_cost = (
                    self.landed_cost_factor
                    * (self.currency_factor or 1)
                    * line.cost_id.cost_lines[0].price_unit
                    if self.landed_cost_factor > 0
                    else line.product_id.standard_price
                )
                computed_price = (
                    self.base_pricing_factor * landed_cost
                    if self.base_pricing_factor > 0
                    else line.product_id.lst_price
                )
                print("===LANDED COST===")
                print(landed_cost)
                line.new_cost = landed_cost
                line.computed_price = computed_price
                purchase_line_id = self.env["purchase.order.line"].search(
                    [
                        ("product_id", "=", line.product_id.id),
                        ("order_id", "=", self.purchase_id.id),
                        ("id", "not in", purchase_order_line_ids),
                    ],
                    limit=1,
                    order="id asc",
                )
                purchase_order_line_ids.append(purchase_line_id.id)
                if (
                    line.cost_line_id.split_method == "equal"
                    and line.quantity != purchase_line_id.product_qty
                    and purchase_line_id.product_qty > 0
                ):
                    line.additional_landed_cost = (
                        line.quantity
                        / purchase_line_id.product_qty
                        * line.additional_landed_cost
                    )
                elif line.cost_line_id.split_method == "by_quantity":
                    line.additional_landed_cost = (
                        line.cost_line_id.price_unit
                        / total_purchase_qty
                        * line.quantity
                    )
                elif line.cost_line_id.split_method == "by_weight":
                    line.additional_landed_cost = (
                        line.cost_line_id.price_unit
                        / total_product_weight
                        * line.quantity
                        * line.product_id.weight
                    )
                elif line.cost_line_id.split_method == "by_volume":
                    line.additional_landed_cost = (
                        line.cost_line_id.price_unit
                        / total_product_volume
                        * line.quantity
                        * line.product_id.volume
                    )
                elif line.cost_line_id.split_method == "by_current_cost_price":
                    line.additional_landed_cost = (
                        line.cost_line_id.price_unit
                        / prev_former_cost
                        * line.former_cost
                    )
                if line.cost_line_id.id not in cost_dict:
                    cost_dict[line.cost_line_id.id] = line.additional_landed_cost
                else:
                    cost_dict[line.cost_line_id.id] += line.additional_landed_cost

            landed_cost_line_obj = self.env["stock.landed.cost.lines"]
            print("\n\n===COST DICT===")
            print(cost_dict)
            for key, value in cost_dict.items():
                print(key, value)
                landed_cost_line_obj.browse(key).write({"price_unit": value})

        return res

    def adjust_costing(self):
        for record in self:
            for line in record.valuation_adjustment_lines:
                line.old_price = line.product_id.lst_price
                line.former_cost = line.product_id.standard_price
                line.product_id.lst_price = line.new_price
                line.product_id.standard_price = line.new_cost

    def revert_costing(self):
        for record in self:
            for line in record.valuation_adjustment_lines:
                line.product_id.lst_price = line.old_price
                line.product_id.standard_price = line.former_cost

    def update_supplier_pricelist(self):
        for record in self:
            for line in record.valuation_adjustment_lines:
                supplier_pricelist = line.product_id.seller_ids.filtered(
                    lambda x: x.id == record.purchase_id.partner_id.id
                )
                if supplier_pricelist:
                    for pricelist in supplier_pricelist:
                        pricelist.purchase_id = record.purchase_id.id
                        for line in pricelist.pricelist_ids:
                            line.price = line.product_id.lst_price

from odoo import fields, models, api, _


# class InheritStockValuationAjdjustmentLines(models.Model):
#     _inherit = "stock.valuation.adjustment.lines"

#     cost_difference = fields.Float(
#         string="Cost Difference", compute="_compute_cost_difference", store=True
#     )
#     price_difference = fields.Float(
#         string="Price Difference", compute="_compute_price_difference", store=True
#     )
#     computed_price = fields.Float(string="Computed Price", readonly=True)
#     new_price = fields.Float(string="New Price")
#     old_price = fields.Float(string="Old Price")
#     new_cost = fields.Float(string="New Cost")

#     @api.depends("new_cost", "former_cost")
#     def _compute_cost_difference(self):
#         for record in self:
#             record.cost_difference = record.final_cost - record.former_cost

#     @api.depends("computed_price", "new_price")
#     def _compute_price_difference(self):
#         for record in self:
#             record.price_difference = record.new_price - record.computed_price

#     @api.onchange("new_price")
#     def onchange_new_price(self):
#         for record in self:
#             record.new_cost = record.quantity * record.new_price


class PurchaseCosting(models.Model):
    _name = "valuation.adjustment.totals"

    cost_id = fields.Many2one("stock.landed.cost")
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    old_cost = fields.Float(string="Old Cost", readonly=True)
    new_cost = fields.Float(string="New Cost", readonly=True)
    old_price = fields.Float(string="Old Price", readonly=True)
    computed_price = fields.Float(string="Computed Price", readonly=True)
    new_price = fields.Float(string="New Price")
    old_margin = fields.Float(string="Old Margin", compute="_compute_old_margin")
    new_margin = fields.Float(string="New Margin", compute="_compute_new_margin")
    cost_difference = fields.Float(
        string="Cost Difference", compute="_compute_cost_difference"
    )
    price_difference = fields.Float(
        string="Price Difference", compute="_compute_price_difference"
    )

    @api.depends("old_cost", "new_cost")
    def _compute_cost_difference(self):
        for record in self:
            record.cost_difference = record.new_cost - record.old_cost

    @api.depends("old_price", "new_price")
    def _compute_price_difference(self):
        for record in self:
            record.price_difference = record.computed_price - record.old_price

    @api.depends("old_cost", "old_price")
    def _compute_old_margin(self):
        for record in self:
            record.old_margin = record.old_price - record.old_cost

    @api.depends("new_cost", "new_price")
    def _compute_new_margin(self):
        for record in self:
            record.new_margin = record.new_price - record.new_cost

    # @api.depends("new_price")
    # def recompute_price_and_margin(self):
    #     self.new_margin = self.new_price - self.new_cost
    #     self.price_difference = self.new_price - self.old_price

    @api.depends("old_price", "old_cost", "new_cost")
    def _compute_price(self):
        for record in self:
            record.computed_price = record.old_price + record.cost_difference

    # @api.depends("product_id")
    # def compute_old_cost(self):
    #     for record in self:
    #         record.old_cost = (
    #             sum(self.cost_id.stock_valuation_layer_ids.mapped("value")),
    #         )

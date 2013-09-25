qx.Bootstrap.define("qx.module.ui.Rating", {
  extend : qx.module.ui.Widget,


  statics : {
    _templates : {
      symbol : "★"
    },

    _config : {
      length : 5
    }
  },


  construct : function(selector, context) {
    this.base(arguments, selector, context);

    this.forEach(function(rating) {
      rating = q(rating);

      for (var i = 0; i < this.getConfig("length"); i++) {
        q.create("<span>" + this.getTemplate("symbol") + "</span>").appendTo(rating);
      }

      rating.getChildren("span")
        .addClasses(["qx-rating", "qx-rating-off"])
        .on("click", this.__onClick, this);
    }.bind(this));

  },


  members : {
    setValue : function(value) {
      var children = this.getChildren("span");
      children.removeClass("qx-rating-off");
      children.slice(value, children.length).addClass("qx-rating-off");
      this.emit("changeValue", this.getValue());
    },


    getValue : function() {
      return this.getChildren("span").not(".qx-rating-off").length;
    },


    render : function() {
      var length = this.getConfig("length");
      this.forEach(function(el) {
        el = q(el);
        var children = el.getChildren();
        children.setHtml(this.getTemplate("symbol"));
        var diff = length - children.length;
        if (diff > 0) {
          for (var i = 0; i < diff; i++) {
            children.getLast().clone(true).appendTo(el);
          }
        } else {
          for (var i = 0; i < Math.abs(diff); i++) {
            el.getChildren().getLast().remove();
          }
        }
      }.bind(this));
      return this;
    },


    __onClick : function(e) {
      var parents = q(e.target).getParents();
      this.setValue(parents.getChildren().indexOf(e.target) + 1);
    }
  },


  defer : function(statics) {
    qxWeb.$attach({
      rating : function(initValue, symbol, length) {
        var rating =  new qx.module.ui.Rating(this);

        var modified = false;
        if (length != undefined && length != rating.getConfig("length")) {
          rating.setConfig("length", length);
          modified = true;
        }

        if (symbol != undefined) {
          rating.setTemplate("symbol", symbol);
          modified = true;
        }

        if (modified) {
          rating.render();
        }

        if (initValue != undefined) {
          rating.setValue(initValue);
        }

        return rating;
      }
    });
  }
});

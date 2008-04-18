/* ************************************************************************

   qooxdoo - the new era of web development

   http://qooxdoo.org

   Copyright:
     2004-2008 1&1 Internet AG, Germany, http://www.1und1.de

   License:
     LGPL: http://www.gnu.org/licenses/lgpl.html
     EPL: http://www.eclipse.org/org/documents/epl-v10.php
     See the LICENSE file in the project's top-level directory for details.

   Authors:
     * Sebastian Werner (wpbasti)
     * Fabian Jakobs (fjakobs)

************************************************************************ */

qx.Class.define("demobrowser.demo.layout.HBoxLayout_2",
{
  extend : qx.application.Standalone,

  members :
  {
    main: function()
    {
      this.base(arguments);

      // auto size + negative margins
      var box = new qx.ui.layout.HBox();
      var container = (new qx.ui.container.Composite(box)).set({decorator: "black", backgroundColor: "yellow", height:80});

      var w1 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "blue", maxHeight: 50});
      var w2 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "green", maxHeight: 50});
      var w3 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "grey", maxHeight: 50});

      container.add(w1, { align : "top" });
      container.add(w2, { align : "middle", marginLeft : -10 });
      container.add(w3, { align : "bottom", marginLeft : -10 });

      this.getRoot().add(container, {left:10, top:10});




      // auto size + negative margins + collapsing
      var box = new qx.ui.layout.HBox();
      var container = (new qx.ui.container.Composite(box)).set({decorator: "black", backgroundColor: "yellow", height:80});

      var w1 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "blue", maxHeight: 50});
      var w2 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "green", maxHeight: 50});
      var w3 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "grey", maxHeight: 50});

      container.add(w1, { align : "top" });
      container.add(w2, { align : "middle", marginLeft : -10, marginRight : 20 });
      container.add(w3, { align : "bottom", marginLeft : -10 });

      this.getRoot().add(container, {left:10, top:100});




      // auto size + negative margins + flex
      var box = new qx.ui.layout.HBox();
      var container = (new qx.ui.container.Composite(box)).set({decorator: "black", backgroundColor: "yellow", height:80, width: 500});

      var w1 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "blue", maxHeight: 50});
      var w2 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "green", maxHeight: 50});
      var w3 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "grey", maxHeight: 50});

      container.add(w1, { flex : 1, align : "top" });
      container.add(w2, { flex : 1, align : "middle", marginLeft : -10 });
      container.add(w3, { flex : 1, align : "bottom", marginLeft : -10 });

      this.getRoot().add(container, {left:10, top:190});





      // auto size + negative margins + different flex
      var box = new qx.ui.layout.HBox();
      var container = (new qx.ui.container.Composite(box)).set({decorator: "black", backgroundColor: "yellow", height:80, width: 500});

      var w1 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "blue", maxHeight: 50});
      var w2 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "green", maxHeight: 50});
      var w3 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "grey", maxHeight: 50});

      container.add(w1, { flex : 1, align : "top" });
      container.add(w2, { flex : 2, align : "middle", marginLeft : -10 });
      container.add(w3, { flex : 3, align : "bottom", marginLeft : -10 });

      this.getRoot().add(container, {left:10, top:280});




      // auto size + negative margins + different flex (using width)
      var box = new qx.ui.layout.HBox();
      var container = (new qx.ui.container.Composite(box)).set({decorator: "black", backgroundColor: "yellow", height:80, width: 500});

      var w1 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "blue", maxHeight: 50});
      var w2 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "green", maxHeight: 50});
      var w3 = (new qx.ui.core.Widget).set({decorator: "black", backgroundColor: "grey", maxHeight: 50});

      container.add(w1, { width : "1*", align : "top" });
      container.add(w2, { width : "2*", align : "middle", marginLeft : -10 });
      container.add(w3, { width : "3*", align : "bottom", marginLeft : -10 });

      this.getRoot().add(container, {left:10, top:370});
    }
  }
});

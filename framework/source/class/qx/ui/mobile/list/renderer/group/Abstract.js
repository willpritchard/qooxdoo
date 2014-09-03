"use strict";
/* ************************************************************************

   qooxdoo - the new era of web development

   http://qooxdoo.org

   Copyright:
     2004-2014 1&1 Internet AG, Germany, http://www.1und1.de

   License:
     LGPL: http://www.gnu.org/licenses/lgpl.html
     EPL: http://www.eclipse.org/org/documents/epl-v10.php
     See the LICENSE file in the project's top-level directory for details.

   Authors:
     * Christopher Zuendorf (czuendorf)

************************************************************************ */

/**
 * Base class for all group item renderer.
 */
qx.Bootstrap.define("qx.ui.mobile.list.renderer.group.Abstract",
{
  extend : qx.ui.mobile.core.Widget,


  construct : function(layout)
  {
    this.base(qx.ui.mobile.core.Widget, "constructor");
    this.setLayout(layout);
    this.selectable = undefined;
  },


  properties :
  {
    // overridden
    defaultCssClass :
    {
      init : "group-item"
    },

    /**
     * Whether the row is selectable.
     */
    selectable :
    {
      check : "Boolean",
      init : false,
      apply : "_applySelectable"
    },


    //overridden
    activatable :
    {
      refine :true,
      init : true
    }
  },


  members :
  {
    // abstract method
    /**
     * Resets all defined child widgets. Override this method in your custom
     * list item renderer and reset all widgets displaying data. Needed as the
     * renderer is used for every row and otherwise data of a different row
     * might be displayed, when not all data displaying widgets are used for the row.
     * Gets called automatically by the {@link qx.ui.mobile.list.provider.Provider}.
     *
     */
    reset : function() {
      if (qx.core.Environment.get("qx.debug")) {
        throw new Error("Abstract method call");
      }
    },


    // overridden
    _getTagName : function()
    {
      return "li";
    }
  }
});